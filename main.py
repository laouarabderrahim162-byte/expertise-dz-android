# -*- coding: utf-8 -*-
"""
Expertise DZ AirGIS — تطبيق أندرويد (Kivy)
نواة مبسطة تعيد نفس منطق نسخة Windows (app.py):
- إدارة القضايا
- إدارة المهام المرتبطة بالقضية (مع علامة AirGIS)
- إدارة الوثائق + حساب SHA-256
- تسجيل رحلات الطيران (GSD / RTK)
- سلسلة الحفظ الرقمي (Digital Evidence Chain)
- توليد مسودة تقرير نصي
- قاعدة بيانات محلية SQLite (بدون إنترنت)
"""

import os
import sqlite3
import hashlib
import datetime

from kivy.app import App
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.checkbox import CheckBox
from kivy.uix.spinner import Spinner
from kivy.uix.popup import Popup
from kivy.uix.filechooser import FileChooserListView
from kivy.metrics import dp
from kivy.core.text import LabelBase

DB_PATH = os.path.join(App.get_running_app().user_data_dir, "expertise_dz.db") \
    if False else "expertise_dz.db"  # يُستبدل فعليًا داخل on_start


# ===================== قاعدة البيانات =====================
class DB:
    def __init__(self, path):
        self.path = path
        self.conn = sqlite3.connect(self.path)
        self.conn.execute("PRAGMA foreign_keys = ON")
        self._init_schema()

    def _init_schema(self):
        c = self.conn.cursor()
        c.execute("""CREATE TABLE IF NOT EXISTS cases(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT, court TEXT, client TEXT, created_at TEXT
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS tasks(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            case_id INTEGER, title TEXT, needs_air INTEGER,
            status TEXT, created_at TEXT
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS docs(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            case_id INTEGER, name TEXT, sha256 TEXT,
            chain_hash TEXT, prev_hash TEXT, added_at TEXT
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS flights(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            case_id INTEGER, gsd TEXT, rtk TEXT, notes TEXT,
            hash TEXT, chain_hash TEXT, prev_hash TEXT, added_at TEXT
        )""")
        self.conn.commit()

    def now(self):
        return datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

    # ---- cases ----
    def add_case(self, title, court, client):
        self.conn.execute(
            "INSERT INTO cases(title, court, client, created_at) VALUES(?,?,?,?)",
            (title, court, client, self.now()))
        self.conn.commit()

    def list_cases(self):
        return self.conn.execute("SELECT id, title, court, client, created_at FROM cases").fetchall()

    def delete_case(self, case_id):
        self.conn.execute("DELETE FROM cases WHERE id=?", (case_id,))
        self.conn.execute("DELETE FROM tasks WHERE case_id=?", (case_id,))
        self.conn.execute("DELETE FROM docs WHERE case_id=?", (case_id,))
        self.conn.execute("DELETE FROM flights WHERE case_id=?", (case_id,))
        self.conn.commit()

    # ---- tasks ----
    def add_task(self, case_id, title, needs_air):
        self.conn.execute(
            "INSERT INTO tasks(case_id, title, needs_air, status, created_at) VALUES(?,?,?,?,?)",
            (case_id, title, int(needs_air), "قيد التنفيذ", self.now()))
        self.conn.commit()

    def list_tasks(self, case_id=None):
        if case_id:
            return self.conn.execute(
                "SELECT id, title, needs_air, status, created_at FROM tasks WHERE case_id=?",
                (case_id,)).fetchall()
        return self.conn.execute(
            "SELECT id, title, needs_air, status, created_at FROM tasks").fetchall()

    def toggle_task(self, task_id):
        row = self.conn.execute("SELECT status FROM tasks WHERE id=?", (task_id,)).fetchone()
        new_status = "منجزة" if row[0] != "منجزة" else "قيد التنفيذ"
        self.conn.execute("UPDATE tasks SET status=? WHERE id=?", (new_status, task_id))
        self.conn.commit()

    # ---- evidence chain helpers ----
    def last_chain_hash(self, case_id):
        rows = list(self.conn.execute(
            "SELECT chain_hash, added_at FROM docs WHERE case_id=?", (case_id,))) + \
            list(self.conn.execute(
            "SELECT chain_hash, added_at FROM flights WHERE case_id=?", (case_id,)))
        if not rows:
            return "GENESIS"
        rows.sort(key=lambda r: r[1])
        return rows[-1][0]

    # ---- docs ----
    def add_doc(self, case_id, name, file_bytes=None):
        if file_bytes is not None:
            sha = hashlib.sha256(file_bytes).hexdigest()
        else:
            sha = hashlib.sha256((name + str(datetime.datetime.now())).encode("utf-8")).hexdigest()
        prev = self.last_chain_hash(case_id)
        chain = hashlib.sha256((prev + "|" + sha).encode("utf-8")).hexdigest()
        self.conn.execute(
            "INSERT INTO docs(case_id, name, sha256, chain_hash, prev_hash, added_at) VALUES(?,?,?,?,?,?)",
            (case_id, name, sha, chain, prev, self.now()))
        self.conn.commit()

    def list_docs(self, case_id):
        return self.conn.execute(
            "SELECT id, name, sha256, added_at FROM docs WHERE case_id=?", (case_id,)).fetchall()

    # ---- flights ----
    def add_flight(self, case_id, gsd, rtk, notes):
        summary = f"GSD:{gsd}|RTK:{rtk}|{notes}|{datetime.datetime.now()}"
        h = hashlib.sha256(summary.encode("utf-8")).hexdigest()
        prev = self.last_chain_hash(case_id)
        chain = hashlib.sha256((prev + "|" + h).encode("utf-8")).hexdigest()
        self.conn.execute(
            "INSERT INTO flights(case_id, gsd, rtk, notes, hash, chain_hash, prev_hash, added_at) VALUES(?,?,?,?,?,?,?,?)",
            (case_id, gsd, rtk, notes, h, chain, prev, self.now()))
        self.conn.commit()

    def list_flights(self, case_id):
        return self.conn.execute(
            "SELECT id, gsd, rtk, notes, hash, added_at FROM flights WHERE case_id=?",
            (case_id,)).fetchall()

    def chain_for_case(self, case_id):
        items = []
        for r in self.conn.execute(
                "SELECT name, sha256, chain_hash, added_at FROM docs WHERE case_id=?", (case_id,)):
            items.append(("وثيقة: " + r[0], r[1], r[2], r[3]))
        for r in self.conn.execute(
                "SELECT gsd, rtk, hash, chain_hash, added_at FROM flights WHERE case_id=?", (case_id,)):
            items.append((f"رحلة GSD={r[0]} RTK={r[1]}", r[2], r[3], r[4]))
        items.sort(key=lambda x: x[3])
        return items


# ===================== واجهات مساعدة =====================
def list_row(text, on_press=None, meta=None):
    box = BoxLayout(orientation="vertical", size_hint_y=None, height=dp(64), padding=dp(4))
    box.add_widget(Label(text=text, halign="right", valign="middle"))
    if meta:
        box.add_widget(Label(text=meta, font_size="11sp", color=(0.6, 0.6, 0.6, 1)))
    return box


class BaseScreen(Screen):
    def scroll_list(self):
        sv = ScrollView()
        grid = GridLayout(cols=1, size_hint_y=None, spacing=dp(6), padding=dp(6))
        grid.bind(minimum_height=grid.setter("height"))
        sv.add_widget(grid)
        return sv, grid


# ===================== شاشة القضايا =====================
class CasesScreen(BaseScreen):
    def __init__(self, db, **kw):
        super().__init__(**kw)
        self.db = db
        root = BoxLayout(orientation="vertical", padding=dp(10), spacing=dp(6))

        self.title_in = TextInput(hint_text="عنوان / رقم القضية", size_hint_y=None, height=dp(44))
        self.court_in = TextInput(hint_text="المحكمة", size_hint_y=None, height=dp(44))
        self.client_in = TextInput(hint_text="الموكل", size_hint_y=None, height=dp(44))
        add_btn = Button(text="حفظ القضية", size_hint_y=None, height=dp(46))
        add_btn.bind(on_press=self.add_case)

        root.add_widget(Label(text="القضايا", font_size="20sp", size_hint_y=None, height=dp(36)))
        root.add_widget(self.title_in)
        root.add_widget(self.court_in)
        root.add_widget(self.client_in)
        root.add_widget(add_btn)

        self.sv, self.grid = self.scroll_list()
        root.add_widget(self.sv)
        self.add_widget(root)
        self.refresh()

    def add_case(self, *_):
        if not self.title_in.text.strip():
            return
        self.db.add_case(self.title_in.text.strip(), self.court_in.text.strip(), self.client_in.text.strip())
        self.title_in.text = self.court_in.text = self.client_in.text = ""
        self.refresh()
        self.manager.get_screen("tasks").refresh_case_list()
        self.manager.get_screen("docs").refresh_case_list()
        self.manager.get_screen("flights").refresh_case_list()
        self.manager.get_screen("report").refresh_case_list()

    def refresh(self):
        self.grid.clear_widgets()
        for row in self.db.list_cases():
            cid, title, court, client, created = row
            meta = f"{court or ''}  {client or ''}  {created}"
            item = list_row(title, meta=meta)
            del_btn = Button(text="حذف", size_hint=(None, None), size=(dp(60), dp(34)))
            del_btn.bind(on_press=lambda b, i=cid: self.delete(i))
            item.add_widget(del_btn)
            self.grid.add_widget(item)

    def delete(self, cid):
        self.db.delete_case(cid)
        self.refresh()


# ===================== شاشة المهام =====================
class TasksScreen(BaseScreen):
    def __init__(self, db, **kw):
        super().__init__(**kw)
        self.db = db
        self.case_map = {}
        root = BoxLayout(orientation="vertical", padding=dp(10), spacing=dp(6))

        self.case_spinner = Spinner(text="اختر قضية", size_hint_y=None, height=dp(44))
        self.case_spinner.bind(text=lambda *_: self.refresh())
        self.title_in = TextInput(hint_text="وصف المهمة", size_hint_y=None, height=dp(44))
        self.needs_air = CheckBox(size_hint_y=None, height=dp(30))
        air_row = BoxLayout(size_hint_y=None, height=dp(30))
        air_row.add_widget(Label(text="تحتاج AirGIS"))
        air_row.add_widget(self.needs_air)
        add_btn = Button(text="إضافة مهمة", size_hint_y=None, height=dp(46))
        add_btn.bind(on_press=self.add_task)

        root.add_widget(Label(text="المهام", font_size="20sp", size_hint_y=None, height=dp(36)))
        root.add_widget(self.case_spinner)
        root.add_widget(self.title_in)
        root.add_widget(air_row)
        root.add_widget(add_btn)

        self.sv, self.grid = self.scroll_list()
        root.add_widget(self.sv)
        self.add_widget(root)

    def on_pre_enter(self):
        self.refresh_case_list()

    def refresh_case_list(self):
        self.case_map = {c[1]: c[0] for c in self.db.list_cases()}
        self.case_spinner.values = list(self.case_map.keys()) or ["لا توجد قضايا"]
        self.refresh()

    def add_task(self, *_):
        cid = self.case_map.get(self.case_spinner.text)
        if not cid or not self.title_in.text.strip():
            return
        self.db.add_task(cid, self.title_in.text.strip(), self.needs_air.active)
        self.title_in.text = ""
        self.needs_air.active = False
        self.refresh()

    def refresh(self):
        self.grid.clear_widgets()
        cid = self.case_map.get(self.case_spinner.text)
        if not cid:
            return
        for row in self.db.list_tasks(cid):
            tid, title, needs_air, status, created = row
            meta = f"{status}  {'🚁 AirGIS' if needs_air else ''}  {created}"
            item = list_row(title, meta=meta)
            btn = Button(text="تبديل", size_hint=(None, None), size=(dp(60), dp(34)))
            btn.bind(on_press=lambda b, i=tid: (self.db.toggle_task(i), self.refresh()))
            item.add_widget(btn)
            self.grid.add_widget(item)


# ===================== شاشة الوثائق =====================
class DocsScreen(BaseScreen):
    def __init__(self, db, **kw):
        super().__init__(**kw)
        self.db = db
        self.case_map = {}
        root = BoxLayout(orientation="vertical", padding=dp(10), spacing=dp(6))

        self.case_spinner = Spinner(text="اختر قضية", size_hint_y=None, height=dp(44))
        self.case_spinner.bind(text=lambda *_: self.refresh())
        self.name_in = TextInput(hint_text="اسم الوثيقة", size_hint_y=None, height=dp(44))
        pick_btn = Button(text="اختيار ملف وحساب SHA-256", size_hint_y=None, height=dp(46))
        pick_btn.bind(on_press=self.open_filechooser)
        manual_btn = Button(text="إضافة بدون ملف (بصمة رمزية)", size_hint_y=None, height=dp(40))
        manual_btn.bind(on_press=lambda *_: self.add_doc(None))

        root.add_widget(Label(text="الوثائق", font_size="20sp", size_hint_y=None, height=dp(36)))
        root.add_widget(self.case_spinner)
        root.add_widget(self.name_in)
        root.add_widget(pick_btn)
        root.add_widget(manual_btn)

        self.sv, self.grid = self.scroll_list()
        root.add_widget(self.sv)
        self.add_widget(root)

    def on_pre_enter(self):
        self.refresh_case_list()

    def refresh_case_list(self):
        self.case_map = {c[1]: c[0] for c in self.db.list_cases()}
        self.case_spinner.values = list(self.case_map.keys()) or ["لا توجد قضايا"]
        self.refresh()

    def open_filechooser(self, *_):
        chooser = FileChooserListView(path=os.path.expanduser("~"))
        popup = Popup(title="اختر ملفًا", content=chooser, size_hint=(0.9, 0.9))

        def chosen(instance, selection, touch):
            if selection:
                popup.dismiss()
                with open(selection[0], "rb") as f:
                    data = f.read()
                name = self.name_in.text.strip() or os.path.basename(selection[0])
                self.add_doc(data, name)

        chooser.bind(on_submit=chosen)
        popup.open()

    def add_doc(self, file_bytes, name=None):
        cid = self.case_map.get(self.case_spinner.text)
        if not cid:
            return
        final_name = name or self.name_in.text.strip() or "وثيقة بدون اسم"
        self.db.add_doc(cid, final_name, file_bytes)
        self.name_in.text = ""
        self.refresh()

    def refresh(self):
        self.grid.clear_widgets()
        cid = self.case_map.get(self.case_spinner.text)
        if not cid:
            return
        for row in self.db.list_docs(cid):
            did, name, sha, added = row
            meta = f"SHA-256: {sha[:24]}...  {added}"
            self.grid.add_widget(list_row(name, meta=meta))


# ===================== شاشة الطيران =====================
class FlightsScreen(BaseScreen):
    def __init__(self, db, **kw):
        super().__init__(**kw)
        self.db = db
        self.case_map = {}
        root = BoxLayout(orientation="vertical", padding=dp(10), spacing=dp(6))

        self.case_spinner = Spinner(text="اختر قضية", size_hint_y=None, height=dp(44))
        self.case_spinner.bind(text=lambda *_: self.refresh())
        self.gsd_in = TextInput(hint_text="GSD (سم/بكسل)", size_hint_y=None, height=dp(44), input_filter="float")
        self.rtk_in = TextInput(hint_text="دقة RTK (سم)", size_hint_y=None, height=dp(44), input_filter="float")
        self.notes_in = TextInput(hint_text="ملاحظات الرحلة", size_hint_y=None, height=dp(70), multiline=True)
        add_btn = Button(text="حفظ بيانات الرحلة", size_hint_y=None, height=dp(46))
        add_btn.bind(on_press=self.add_flight)

        root.add_widget(Label(text="بيانات الطيران", font_size="20sp", size_hint_y=None, height=dp(36)))
        root.add_widget(self.case_spinner)
        root.add_widget(self.gsd_in)
        root.add_widget(self.rtk_in)
        root.add_widget(self.notes_in)
        root.add_widget(add_btn)

        self.sv, self.grid = self.scroll_list()
        root.add_widget(self.sv)
        self.add_widget(root)

    def on_pre_enter(self):
        self.refresh_case_list()

    def refresh_case_list(self):
        self.case_map = {c[1]: c[0] for c in self.db.list_cases()}
        self.case_spinner.values = list(self.case_map.keys()) or ["لا توجد قضايا"]
        self.refresh()

    def add_flight(self, *_):
        cid = self.case_map.get(self.case_spinner.text)
        if not cid:
            return
        self.db.add_flight(cid, self.gsd_in.text.strip(), self.rtk_in.text.strip(), self.notes_in.text.strip())
        self.gsd_in.text = self.rtk_in.text = self.notes_in.text = ""
        self.refresh()

    def refresh(self):
        self.grid.clear_widgets()
        cid = self.case_map.get(self.case_spinner.text)
        if not cid:
            return
        for row in self.db.list_flights(cid):
            fid, gsd, rtk, notes, h, added = row
            meta = f"GSD={gsd} RTK={rtk}  {added}"
            self.grid.add_widget(list_row(notes or "رحلة بدون ملاحظات", meta=meta))


# ===================== شاشة التقرير =====================
class ReportScreen(BaseScreen):
    def __init__(self, db, **kw):
        super().__init__(**kw)
        self.db = db
        self.case_map = {}
        root = BoxLayout(orientation="vertical", padding=dp(10), spacing=dp(6))

        self.case_spinner = Spinner(text="اختر قضية", size_hint_y=None, height=dp(44))
        gen_btn = Button(text="توليد مسودة التقرير", size_hint_y=None, height=dp(46))
        gen_btn.bind(on_press=self.generate)

        root.add_widget(Label(text="التقارير", font_size="20sp", size_hint_y=None, height=dp(36)))
        root.add_widget(self.case_spinner)
        root.add_widget(gen_btn)

        self.sv = ScrollView()
        self.report_label = Label(text="", size_hint_y=None, halign="right", valign="top")
        self.report_label.bind(texture_size=lambda *_: setattr(
            self.report_label, "height", self.report_label.texture_size[1]))
        self.report_label.bind(width=lambda *_: self.report_label.setter("text_size")(
            self.report_label, (self.report_label.width, None)))
        self.sv.add_widget(self.report_label)
        root.add_widget(self.sv)

        self.add_widget(root)

    def on_pre_enter(self):
        self.refresh_case_list()

    def refresh_case_list(self):
        self.case_map = {c[1]: c[0] for c in self.db.list_cases()}
        self.case_spinner.values = list(self.case_map.keys()) or ["لا توجد قضايا"]

    def generate(self, *_):
        cid = self.case_map.get(self.case_spinner.text)
        if not cid:
            return
        case = next(c for c in self.db.list_cases() if c[0] == cid)
        tasks = self.db.list_tasks(cid)
        docs = self.db.list_docs(cid)
        flights = self.db.list_flights(cid)
        chain = self.db.chain_for_case(cid)

        lines = []
        lines.append("تقرير خبرة تمهيدي — مسودة آلية")
        lines.append("=" * 30)
        lines.append(f"القضية: {case[1]}")
        if case[2]:
            lines.append(f"المحكمة: {case[2]}")
        if case[3]:
            lines.append(f"الموكل: {case[3]}")
        lines.append(f"تاريخ التوليد: {self.db.now()}")
        lines.append("")
        lines.append("أولًا: المهام")
        for t in tasks:
            lines.append(f"- {t[1]} ({t[3]}){'  [AirGIS]' if t[2] else ''}")
        lines.append("")
        lines.append("ثانيًا: بيانات الطيران")
        for f in flights:
            lines.append(f"- GSD={f[1]} RTK={f[2]}  {f[3] or ''}")
        lines.append("")
        lines.append("ثالثًا: الوثائق")
        for d in docs:
            lines.append(f"- {d[1]}  SHA-256: {d[2]}")
        lines.append("")
        lines.append("رابعًا: سلسلة الحفظ الرقمي")
        lines.append(f"عدد العناصر: {len(chain)}")
        lines.append(f"آخر بصمة سلسلة: {self.db.last_chain_hash(cid)}")

        self.report_label.text = "\n".join(lines)


# ===================== شريط التنقل =====================
class NavBar(BoxLayout):
    def __init__(self, sm, **kw):
        super().__init__(size_hint_y=None, height=dp(50), **kw)
        names = [("القضايا", "cases"), ("المهام", "tasks"), ("الوثائق", "docs"),
                 ("الطيران", "flights"), ("التقرير", "report")]
        for label, screen in names:
            b = Button(text=label)
            b.bind(on_press=lambda btn, s=screen: setattr(sm, "current", s))
            self.add_widget(b)


class RootLayout(BoxLayout):
    pass


# ===================== التطبيق =====================
class ExpertiseDZApp(App):
    def build(self):
        db_file = os.path.join(self.user_data_dir, "expertise_dz.db")
        self.db = DB(db_file)

        sm = ScreenManager()
        sm.add_widget(CasesScreen(self.db, name="cases"))
        sm.add_widget(TasksScreen(self.db, name="tasks"))
        sm.add_widget(DocsScreen(self.db, name="docs"))
        sm.add_widget(FlightsScreen(self.db, name="flights"))
        sm.add_widget(ReportScreen(self.db, name="report"))

        root = BoxLayout(orientation="vertical")
        root.add_widget(sm)
        root.add_widget(NavBar(sm))
        return root


if __name__ == "__main__":
    ExpertiseDZApp().run()
