# 🎯 Langkah-Langkah Pengerjaan UAS

## ✅ Yang Sudah Selesai

Semua kode dan dokumentasi sudah lengkap! Anda tinggal menjalankan dan membuat video demo.

**File yang sudah dibuat:**
- ✅ Aggregator service (FastAPI + Worker + Database)
- ✅ Publisher service (Generator + Duplicate simulation)
- ✅ Docker Compose + Dockerfiles
- ✅ 18 Unit & Integration Tests
- ✅ Laporan Teori (T1-T10)
- ✅ README lengkap dengan API docs
- ✅ Quickstart guide
- ✅ Video demo script
- ✅ K6 load test script
- ✅ PowerShell helper scripts

---

## 📋 TODO: Yang Perlu Anda Lakukan

### 1️⃣ Test Sistem (30 menit)

```powershell
# Buka PowerShell
cd "c:\Users\Admin\OneDrive\Documents\ITK\Semester 7\Uas Sister"

# Load helper scripts
. .\scripts.ps1

# Start semua services
Start-Services

# Tunggu 2 menit untuk publisher selesai
Start-Sleep -Seconds 120

# Check hasil
Get-Stats
Get-Events -Limit 5

# Run tests
Invoke-Tests

# Demo features
Test-Deduplication
Test-Persistence
```

**Lihat:** [QUICKSTART.md](QUICKSTART.md) dan [POWERSHELL_GUIDE.md](POWERSHELL_GUIDE.md)

---

### 2️⃣ Lengkapi Laporan (1-2 jam)

Buka `LAPORAN.md` dan lengkapi:

**Bagian yang perlu diisi:**
- [ ] **Identitas**: Nama, NIM, Kelas
- [ ] **T1-T10**: Review jawaban, tambah penjelasan jika perlu (template sudah ada 150-250 kata per soal)
- [ ] **Screenshot**: Tambah gambar hasil testing, stats, logs
- [ ] **Diagram**: Tambah arsitektur diagram (bisa pakai draw.io)
- [ ] **Metrics**: Tambah hasil performance dari K6 load test
- [ ] **Sitasi**: Update referensi buku dengan metadata lengkap (ganti `docs/buku-utama.pdf` dengan info buku yang benar)

**Contoh sitasi APA 7th:**
```
Tanenbaum, A. S., & Van Steen, M. (2017). Distributed systems: Principles and paradigms (3rd ed.). Pearson.
```

**Lihat:** Template lengkap di [LAPORAN.md](LAPORAN.md)

---

### 3️⃣ Rekam Video Demo (maksimal 25 menit)

Ikuti script lengkap di [VIDEO_DEMO_SCRIPT.md](VIDEO_DEMO_SCRIPT.md).

**Timeline:**
```
00:00-02:00  - Intro & Arsitektur
02:00-04:00  - Docker Compose & Services
04:00-08:00  - Idempotency Demo
08:00-12:00  - Concurrency Demo
12:00-16:00  - Transaction & Deduplication
16:00-19:00  - Persistence Demo
19:00-22:00  - Testing (18 tests)
22:00-24:00  - Monitoring & Observability
24:00-25:00  - Penutup
```

**Tools untuk recording:**
- OBS Studio (gratis)
- ShareX (gratis)
- Windows Game Bar (Win+G)

**Upload ke YouTube:**
- Bisa unlisted atau public
- Tambah deskripsi dengan link GitHub
- Copy link untuk laporan

---

### 4️⃣ Push ke GitHub (15 menit)

```powershell
# Di project directory
cd "c:\Users\Admin\OneDrive\Documents\ITK\Semester 7\Uas Sister"

# Init repository
git init
git add .
git commit -m "Initial commit: Pub-Sub Log Aggregator System"

# Create repo di GitHub (via browser)
# https://github.com/new
# Nama repo: pub-sub-log-aggregator

# Push ke GitHub
git remote add origin https://github.com/USERNAME/pub-sub-log-aggregator.git
git branch -M main
git push -u origin main
```

**Verifikasi:**
- [ ] README.md tampil dengan baik
- [ ] Semua file ter-upload
- [ ] Link video demo ada di README

---

### 5️⃣ Submit Deliverables

**3 Deliverables:**
1. **GitHub URL**: https://github.com/USERNAME/pub-sub-log-aggregator
2. **Laporan**: LAPORAN.md atau export ke PDF
3. **Video Demo**: YouTube link (di README.md)

---

## 🔥 Quick Commands Cheat Sheet

### PowerShell (Windows)

```powershell
# Load scripts
. .\scripts.ps1

# Start system
Start-Services

# Check status
Test-Health
Get-Stats

# View data
Get-Events
Get-Events -Topic "user.login"

# Test features
Test-Deduplication
Test-Persistence

# Run tests
Invoke-Tests

# View logs
Show-Logs
Show-Logs -Service aggregator

# Stop (keep data)
Stop-Services

# Stop + cleanup
Stop-ServicesClean
```

### CMD / Manual Docker Commands

```bash
# Start
docker compose up --build -d

# Check status
docker compose ps
curl http://localhost:8080/health
curl http://localhost:8080/stats

# Run tests
pip install -r tests/requirements.txt
pytest tests/ -v

# View logs
docker compose logs -f aggregator

# Stop
docker compose down

# Stop + remove volumes
docker compose down -v
```

---

## 📊 Rubric Checklist

### Teori (30 poin)

- [ ] T1: Penjelasan sistem terdistribusi (3 poin)
- [ ] T2: Karakteristik sistem terdistribusi (3 poin)
- [ ] T3: Middleware layer (3 poin)
- [ ] T4: Komunikasi request-reply (3 poin)
- [ ] T5: Pub-Sub pattern (3 poin)
- [ ] T6: Fault tolerance (3 poin)
- [ ] T7: Consistency & replication (3 poin)
- [ ] T8: ACID transactions ⭐ (3 poin)
- [ ] T9: Concurrency control ⭐ (3 poin)
- [ ] T10: Event-driven architecture (3 poin)

### Implementasi (70 poin)

**Docker & Deployment (15 poin)**
- [x] Docker Compose konfigurasi (5 poin)
- [x] Multi-service orchestration (5 poin)
- [x] Health checks & dependencies (5 poin)

**Core Features (25 poin)**
- [x] Idempotent consumer (7 poin)
- [x] Deduplication mechanism (7 poin)
- [x] ACID transactions (6 poin)
- [x] Concurrency control (5 poin)

**Testing (15 poin)**
- [x] 12-20 tests (sudah ada 18) (10 poin)
- [x] Test coverage: idempotency, concurrency, persistence (5 poin)

**Documentation (10 poin)**
- [x] README with architecture (3 poin)
- [x] API documentation (3 poin)
- [x] Setup & usage guide (4 poin)

**Video Demo (5 poin)**
- [ ] Menjelaskan arsitektur (1 poin)
- [ ] Demo fitur-fitur (3 poin)
- [ ] Live testing (1 poin)

---

## 🎓 Tips Presentasi

### Untuk Laporan

1. **Jelas & Terstruktur**: Gunakan heading, bullet points, numbering
2. **Code Snippets**: Highlight bagian penting dari implementasi
3. **Diagram**: Visualisasi arsitektur dan flow
4. **Screenshot**: Bukti testing dan hasil running
5. **Sitasi**: Minimal 3-5 referensi dengan APA 7th format

### Untuk Video

1. **Audio Jelas**: Gunakan mic yang bagus, ruangan tenang
2. **Screen Recording**: 1080p minimal, font besar agar jelas
3. **Rehearsal**: Latihan 1-2 kali sebelum recording final
4. **Flow**: Ikuti timeline di VIDEO_DEMO_SCRIPT.md
5. **Highlight**: Fokus ke fitur unique: idempotency, concurrency, transactions
6. **Demo Live**: Jalankan test yang show feature works
7. **Professional**: Intro jelas, closing summarize

### Untuk GitHub

1. **README**: Harus informatif, ada badge, screenshot
2. **.gitignore**: Jangan commit __pycache__, .env, venv/
3. **Commit Messages**: Descriptive dan professional
4. **Structure**: Files organized dengan baik
5. **Demo Link**: Video link prominent di README

---

## 📚 File Reference

| File | Purpose |
|------|---------|
| [README.md](README.md) | Main documentation, API specs, architecture |
| [LAPORAN.md](LAPORAN.md) | Theoretical report (T1-T10) |
| [QUICKSTART.md](QUICKSTART.md) | 5-minute setup guide |
| [DEVELOPMENT.md](DEVELOPMENT.md) | Development workflow |
| [VIDEO_DEMO_SCRIPT.md](VIDEO_DEMO_SCRIPT.md) | Video recording timeline |
| [POWERSHELL_GUIDE.md](POWERSHELL_GUIDE.md) | PowerShell commands guide |
| [SUMMARY.md](SUMMARY.md) | Project completion overview |
| [tests/K6_GUIDE.md](tests/K6_GUIDE.md) | Load testing guide |

---

## ⏱️ Estimasi Waktu

| Task | Waktu | Priority |
|------|-------|----------|
| Test sistem local | 30 menit | 🔴 High |
| Lengkapi laporan | 1-2 jam | 🔴 High |
| Rekam video demo | 1-2 jam (include rehearsal) | 🔴 High |
| Push ke GitHub | 15 menit | 🟡 Medium |
| Polish & review | 30 menit | 🟢 Low |

**Total: ~4-6 jam**

---

## 🆘 Troubleshooting Quick Fix

### Docker tidak jalan
```powershell
# Restart Docker Desktop
# Tunggu hingga status "Running"
```

### Port 8080 sudah dipakai
```powershell
# Cari process yang pakai port 8080
netstat -ano | findstr :8080

# Kill process (ganti <PID>)
taskkill /PID <PID> /F
```

### Services tidak healthy
```powershell
# Check logs
docker compose logs aggregator
docker compose logs storage

# Restart specific service
docker compose restart aggregator
```

### Test gagal
```powershell
# Pastikan services running
docker compose ps

# Tunggu aggregator ready
Start-Sleep -Seconds 10

# Run test again
pytest tests/test_aggregator.py -v
```

Lihat troubleshooting lengkap di [README.md#troubleshooting](README.md#troubleshooting).

---

## 🎉 Final Checklist

**Sebelum Submit:**

- [ ] System berjalan tanpa error
- [ ] 18 tests passing
- [ ] Deduplication works (test manual)
- [ ] Persistence works (restart container, data tetap ada)
- [ ] Laporan lengkap (identitas, T1-T10, screenshot, sitasi)
- [ ] Video recorded (<25 menit, audio jelas)
- [ ] Video uploaded ke YouTube
- [ ] GitHub repository created
- [ ] All files pushed to GitHub
- [ ] README updated with video link
- [ ] 3 deliverables ready (GitHub + Laporan + Video)

---

## 📞 Kontak & Support

Jika ada pertanyaan tentang kode atau dokumentasi, bisa:
1. Review file dokumentasi yang relevan
2. Check troubleshooting section
3. Test dengan PowerShell helper commands
4. Review code comments di main.py

---

**Sukses untuk UAS Anda! 🚀**

*"The best way to predict the future is to implement it."*
