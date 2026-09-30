import asyncio
from pathlib import Path
from hustler.db import Database

async def writer_worker(db: Database, stop_event: asyncio.Event, stats: dict):
    # Setup schema
    await db.execute_write("CREATE TABLE IF NOT EXISTS stress_test (id INTEGER PRIMARY KEY AUTOINCREMENT, val TEXT);")
    
    # Sürekli kayıt at
    while not stop_event.is_set():
        try:
            await db.execute_write("INSERT INTO stress_test (val) VALUES (?)", ("test_val",))
            stats["writes"] += 1
            # Arada bir maintenance tetikle
            if stats["writes"] % 100 == 0:
                await db.trigger_maintenance()
        except Exception as e:
            if "database is locked" in str(e).lower():
                stats["locked_errors"] += 1
            else:
                stats["other_errors"] += 1
            await asyncio.sleep(0.01)

async def reader_worker(db: Database, stop_event: asyncio.Event, stats: dict):
    # Bağlantıyı al
    conn = await db.get_reader()
    
    # Sürekli okuma yap
    while not stop_event.is_set():
        try:
            async with conn.execute("SELECT COUNT(*) FROM stress_test;") as cursor:
                await cursor.fetchone()
            stats["reads"] += 1
        except Exception as e:
            if "database is locked" in str(e).lower():
                stats["locked_errors"] += 1
            else:
                stats["other_errors"] += 1
            await asyncio.sleep(0.01)
            
    await conn.close()

async def main():
    db_path = Path("hustler_stress.db")
    if db_path.exists():
        db_path.unlink()
        
    db = Database(db_path)
    await db.init()
    
    stop_event = asyncio.Event()
    stats = {"writes": 0, "reads": 0, "locked_errors": 0, "other_errors": 0}
    
    print("Stres testi başlatılıyor: 1 yazıcı, 5 okuyucu (10 saniye)...")
    
    # 1 Yazıcı başlat
    writer = asyncio.create_task(writer_worker(db, stop_event, stats))
    
    # 5 Okuyucu başlat
    readers = [asyncio.create_task(reader_worker(db, stop_event, stats)) for _ in range(5)]
    
    # 10 saniye bekle
    await asyncio.sleep(10.0)
    stop_event.set()
    
    await writer
    for r in readers:
        await r
        
    await db.close()
    
    print("\n--- STRES TESTİ SONUÇLARI ---")
    print(f"Toplam Yazma İşlemi: {stats['writes']}")
    print(f"Toplam Okuma İşlemi: {stats['reads']}")
    print(f"Database Locked Hataları: {stats['locked_errors']}")
    print(f"Diğer Hatalar: {stats['other_errors']}")
    
    if stats['locked_errors'] == 0:
        print("BAŞARILI: Hiç kilitlenme olmadı. WAL + WriterQueue tasarımı doğru çalışıyor.")
    else:
        print("BAŞARISIZ: Kilitlenme tespit edildi.")
    
    if db_path.exists():
        db_path.unlink()

if __name__ == "__main__":
    asyncio.run(main())
