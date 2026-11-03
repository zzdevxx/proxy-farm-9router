
# Restore DB 9Router dari backup
#
# Setiap run menulis satu cadangan konsisten ke backups/pre-run-<stempel>/
# (memakai SQLite Online Backup API, satu berkas data.sqlite, tanpa -wal/-shm).
# Hanya keep_backups (default 3) yang disimpan; sisanya dibuang otomatis.
#
# Cara pulih manual (9Router harus MATI dulu, jangan while jalan):
#   1. Berhentikan 9Router (tray -> Quit), verifikasi localhost:20128 mati.
#   2. Salin DB aktif saat ini ke backups/manual-<stempel>/ sebagai cadangan lapis dua.
#   3. Salin backups/pre-run-<stempel>/data.sqlite menimpa
#      %APPDATA%\9router\db\data.sqlite.
#   4. Jalankan ulang 9Router.
#
# Verifikasi cadangan tanpa menyentuh DB hidup:
#   python -c "import sqlite3;c=sqlite3.connect('backups/pre-run-<stempel>/data.sqlite');print(c.execute('PRAGMA integrity_check(1)').fetchone()[0])"
