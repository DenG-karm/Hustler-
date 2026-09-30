"""
K-009: Tanılama (hustler doctor)
FFmpeg, SQLite, runs/ boyutu ve CUDA/GPU erişilebilirliğini kontrol eden CLI raporlayıcı.
"""

import shutil
import subprocess
from pathlib import Path

import colorama
from colorama import Fore, Style

def format_size(size_bytes: float) -> str:
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} PB"

def get_dir_size(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(f.stat().st_size for f in path.glob('**/*') if f.is_file())

def check_ffmpeg() -> str:
    path = shutil.which("ffmpeg")
    if path:
        return f"{Fore.GREEN}Bulundu ({path}){Style.RESET_ALL}"
    return f"{Fore.RED}Bulunamadı (PATH'e ekli değil){Style.RESET_ALL}"

def check_cuda() -> str:
    try:
        res = subprocess.run(["nvidia-smi"], capture_output=True, text=True, check=False)
        if res.returncode == 0:
            # Sürücü versiyonunu ve CUDA versiyonunu çek
            first_line = res.stdout.split('\n')[2] if len(res.stdout.split('\n')) > 2 else "Erişilebilir"
            return f"{Fore.GREEN}{first_line.strip()}{Style.RESET_ALL}"
        return f"{Fore.YELLOW}nvidia-smi hata döndürdü (Kod: {res.returncode}){Style.RESET_ALL}"
    except FileNotFoundError:
        return f"{Fore.RED}nvidia-smi bulunamadı (GPU/CUDA mevcut değil veya sürücü eksik){Style.RESET_ALL}"

def run_doctor() -> None:
    colorama.init()
    print(f"{Style.BRIGHT}Hustler Doctor - Sistem Tanılama Raporu{Style.RESET_ALL}\n")
    
    # 1. FFmpeg
    print(f"[{Style.BRIGHT}FFmpeg{Style.RESET_ALL}]: {check_ffmpeg()}")
    
    # 2. CUDA/GPU
    print(f"[{Style.BRIGHT}GPU/CUDA{Style.RESET_ALL}]: {check_cuda()}")
    
    # Yollar
    core_dir = Path(__file__).parent.parent
    db_path = core_dir / "hustler.db"
    runs_dir = core_dir / "runs"
    
    # 3. Veritabanı
    if db_path.exists():
        size = format_size(db_path.stat().st_size)
        print(f"[{Style.BRIGHT}SQLite DB{Style.RESET_ALL}]: {Fore.CYAN}{size}{Style.RESET_ALL} ({db_path})")
    else:
        print(f"[{Style.BRIGHT}SQLite DB{Style.RESET_ALL}]: {Fore.YELLOW}Henüz oluşturulmamış{Style.RESET_ALL}")
        
    # 4. Runs dizini
    if runs_dir.exists():
        size = format_size(get_dir_size(runs_dir))
        print(f"[{Style.BRIGHT}Runs Dizini{Style.RESET_ALL}]: {Fore.CYAN}{size}{Style.RESET_ALL} ({runs_dir})")
    else:
        print(f"[{Style.BRIGHT}Runs Dizini{Style.RESET_ALL}]: {Fore.YELLOW}Henüz oluşturulmamış{Style.RESET_ALL}")
        
    print("\nTanılama tamamlandı.")

if __name__ == "__main__":
    run_doctor()
