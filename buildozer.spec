[app]
title = Expertise DZ AirGIS
package.name = expertisedzairgis
package.domain = org.expertisedz

source.dir = .
source.include_exts = py,png,jpg,kv,atlas

version = 1.0

requirements = python3,kivy

orientation = portrait
fullscreen = 0

# أذونات أندرويد اللازمة لاختيار الملفات وحساب SHA-256 منها
android.permissions = READ_EXTERNAL_STORAGE,WRITE_EXTERNAL_STORAGE

# الحد الأدنى/المستهدف لإصدار أندرويد (buildozer يتكفل بتحميل SDK/NDK تلقائيًا أول مرة)
android.api = 33
android.minapi = 23
android.ndk = 25b

[buildozer]
log_level = 2
warn_on_root = 1
