"""
YouTube Viewer usando Browserless API (sem proxy).
Abre vídeos do YouTube usando navegadores na nuvem do Browserless.
"""

import asyncio
import json
import time
import random
from datetime import datetime
from typing import Optional, Dict, List
from dataclasses import dataclass, field
from threading import Lock
import aiohttp

# =====================================================
# CONFIGURAÇÕES
# =====================================================
BROWSERLESS_API_KEY = "2TaPTUF5ZToCE9je1f1a9658278c6a24cd5b63fda97b64e72"
BROWSERLESS_BASE_URL = "https://production-sfo.browserless.io"

# Proxy (desabilitado)
PROXY_CONFIG = {
    "host": "fb29d01db8530b99.shg.na.pyproxy.io",
    "port": 16666,
    "username": "liderbet1-zone-resi-region-br",
    "password": "Aa10203040"
}


@dataclass
class BrowserSession:
    """Representa uma sessão de navegador."""
    session_id: str
    youtube_url: str
    status: str = "iniciando"
    ip_address: Optional[str] = None
    location: Optional[str] = None
    started_at: datetime = field(default_factory=datetime.now)
    error: Optional[str] = None
    watch_time: int = 0
    title: Optional[str] = None
    
    def to_dict(self):
        return {
            "session_id": self.session_id,
            "youtube_url": self.youtube_url,
            "status": self.status,
            "ip_address": self.ip_address,
            "location": self.location,
            "started_at": self.started_at.strftime("%H:%M:%S"),
            "error": self.error,
            "watch_time": self.watch_time,
            "title": self.title,
            "duration": (datetime.now() - self.started_at).seconds
        }


class BrowserlessManager:
    """Gerencia sessões do Browserless."""
    
    def __init__(self):
        self.sessions: Dict[str, BrowserSession] = {}
        self.lock = Lock()
        self.total_opened = 0
        self.total_success = 0
        self.total_failed = 0
        self.logs: List[dict] = []
        self.max_logs = 200
        self.all_ips: List[Dict] = []
        
    def add_log(self, message: str, level: str = "info"):
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_entry = {"time": timestamp, "message": message, "level": level}
        with self.lock:
            self.logs.insert(0, log_entry)
            if len(self.logs) > self.max_logs:
                self.logs.pop()
        print(f"[{timestamp}] {message}")
    
    def add_session(self, session: BrowserSession):
        with self.lock:
            self.sessions[session.session_id] = session
            self.total_opened += 1
            
    def update_session(self, session_id: str, **kwargs):
        with self.lock:
            if session_id in self.sessions:
                for key, value in kwargs.items():
                    setattr(self.sessions[session_id], key, value)
                    
    def remove_session(self, session_id: str, success: bool = True):
        with self.lock:
            if session_id in self.sessions:
                session = self.sessions[session_id]
                if session.ip_address:
                    self.all_ips.append({
                        "ip": session.ip_address,
                        "location": session.location or "Browserless Cloud",
                        "time": datetime.now().strftime("%H:%M:%S"),
                        "success": success,
                        "url": session.youtube_url[:50]
                    })
                del self.sessions[session_id]
                if success:
                    self.total_success += 1
                else:
                    self.total_failed += 1
    
    def get_stats(self) -> dict:
        with self.lock:
            sessions_list = [s.to_dict() for s in self.sessions.values()]
            active_ips = list(set(s.ip_address for s in self.sessions.values() if s.ip_address))
            return {
                "active_browsers": len(self.sessions),
                "total_opened": self.total_opened,
                "total_success": self.total_success,
                "total_failed": self.total_failed,
                "sessions": sessions_list,
                "active_ips": active_ips,
                "all_ips": self.all_ips[-50:],
                "logs": self.logs[:100]
            }
    
    def reset(self):
        with self.lock:
            self.sessions.clear()
            self.total_opened = 0
            self.total_success = 0
            self.total_failed = 0
            self.logs.clear()
            self.all_ips.clear()


browser_manager = BrowserlessManager()


def gerar_session_id():
    return f"sess_{int(time.time() * 1000)}_{random.randint(1000, 9999)}"


async def open_youtube(youtube_url: str, watch_duration: int = 30) -> bool:
    """
    Abre YouTube usando Browserless API sem proxy.
    """
    session_id = gerar_session_id()
    session = BrowserSession(session_id=session_id, youtube_url=youtube_url)
    browser_manager.add_session(session)
    browser_manager.add_log(f"🚀 Iniciando sessão {session_id[-8:]}...", "info")
    
    # URL da API simples (sem proxy)
    api_url = f"{BROWSERLESS_BASE_URL}/function?token={BROWSERLESS_API_KEY}"
    
    # Script Puppeteer
    puppeteer_code = f"""
    module.exports = async ({{ page }}) => {{
        try {{
            // Configurar viewport
            await page.setViewport({{ width: 1920, height: 1080 }});
            
            // Obter IP atual
            await page.goto('https://ipinfo.io/json', {{ waitUntil: 'networkidle0', timeout: 30000 }});
            const ipText = await page.evaluate(() => document.body.innerText);
            let ipInfo = {{}};
            try {{ ipInfo = JSON.parse(ipText); }} catch(e) {{}}
            
            // Navegar para YouTube
            await page.goto('{youtube_url}', {{ waitUntil: 'domcontentloaded', timeout: 60000 }});
            
            // Obter título
            const title = await page.title();
            
            // Esperar o player carregar e tentar dar play
            try {{
                await page.waitForSelector('video', {{ timeout: 15000 }});
                
                // Fechar diálogos de cookies se aparecerem
                try {{
                    const acceptBtn = await page.$('[aria-label*="Accept"]');
                    if (acceptBtn) await acceptBtn.click();
                }} catch(e) {{}}
                
                // Tentar dar play
                const playBtn = await page.$('.ytp-play-button');
                if (playBtn) {{
                    await playBtn.click();
                }}
            }} catch(e) {{
                // Player pode já estar rodando
            }}
            
            // Simular comportamento humano durante a visualização
            for (let i = 0; i < {watch_duration // 5}; i++) {{
                await new Promise(r => setTimeout(r, 5000));
                const scrollAmount = Math.floor(Math.random() * 200);
                await page.evaluate((s) => window.scrollBy(0, s), scrollAmount);
            }}
            
            return {{
                success: true,
                ip: ipInfo.ip || 'N/A',
                city: ipInfo.city || '',
                region: ipInfo.region || '',
                country: ipInfo.country || '',
                title: title,
                watchTime: {watch_duration}
            }};
        }} catch(error) {{
            return {{ success: false, error: error.message }};
        }}
    }};
    """
    
    try:
        async with aiohttp.ClientSession() as aio_session:
            browser_manager.update_session(session_id, status="conectando ao Browserless")
            browser_manager.add_log(f"🔌 Conectando ao Browserless...", "info")
            
            payload = {"code": puppeteer_code}
            
            async with aio_session.post(
                api_url,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=watch_duration + 120)
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    
                    if result.get("success"):
                        ip = result.get("ip", "N/A")
                        city = result.get("city", "")
                        region = result.get("region", "")
                        country_code = result.get("country", "")
                        title = result.get("title", "Vídeo YouTube")[:80]
                        watch_time = result.get("watchTime", watch_duration)
                        
                        location = f"{city}, {region}" if city else f"{country_code}" if country_code else "USA"
                        browser_manager.update_session(
                            session_id,
                            status="concluído ✓",
                            ip_address=ip,
                            location=location,
                            watch_time=watch_time,
                            title=title
                        )
                        browser_manager.add_log(f"✅ Sucesso! IP: {ip} ({location})", "success")
                        browser_manager.add_log(f"🎬 Título: {title[:50]}...", "success")
                        browser_manager.remove_session(session_id, success=True)
                        return True
                    else:
                        error = result.get("error", "Erro desconhecido")
                        browser_manager.update_session(session_id, status="erro", error=error[:80])
                        browser_manager.add_log(f"❌ Erro: {error[:60]}", "error")
                        browser_manager.remove_session(session_id, success=False)
                        return False
                else:
                    error = await response.text()
                    browser_manager.update_session(session_id, status="erro", error=error[:80])
                    browser_manager.add_log(f"❌ Erro HTTP {response.status}: {error[:60]}", "error")
                    browser_manager.remove_session(session_id, success=False)
                    return False
                    
    except asyncio.TimeoutError:
        browser_manager.update_session(session_id, status="timeout", error="Timeout")
        browser_manager.add_log(f"⏰ Timeout: {session_id[-8:]}", "warning")
        browser_manager.remove_session(session_id, success=False)
        return False
    except Exception as e:
        browser_manager.update_session(session_id, status="erro", error=str(e)[:80])
        browser_manager.add_log(f"❌ Exceção: {str(e)[:60]}", "error")
        browser_manager.remove_session(session_id, success=False)
        return False


async def open_multiple_youtube(youtube_url: str, num_browsers: int = 1, watch_duration: int = 30):
    """Abre múltiplos navegadores simultaneamente."""
    browser_manager.add_log(f"🎬 Iniciando {num_browsers} navegador(es)...", "info")
    browser_manager.add_log(f"📍 URL: {youtube_url[:60]}...", "info")
    browser_manager.add_log(f"⏱️ Duração: {watch_duration}s cada", "info")
    
    tasks = []
    for i in range(num_browsers):
        await asyncio.sleep(0.5)
        task = asyncio.create_task(open_youtube(youtube_url, watch_duration))
        tasks.append(task)
    
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    success_count = sum(1 for r in results if r is True)
    fail_count = num_browsers - success_count
    
    browser_manager.add_log(f"📊 Finalizado: {success_count} ✓ | {fail_count} ✗", "info")
    return success_count, fail_count


def run_youtube_opener(youtube_url: str, num_browsers: int = 1, watch_duration: int = 30):
    """Wrapper síncrono."""
    return asyncio.run(open_multiple_youtube(youtube_url, num_browsers, watch_duration))


if __name__ == "__main__":
    print(f"\n{'='*60}")
    print(f"🎬 YouTube Browserless Viewer")
    print(f"{'='*60}")
    print(f"🔑 API Key: {BROWSERLESS_API_KEY[:20]}...")
    print(f"🌐 Sem proxy - usando IPs do Browserless")
    print(f"{'='*60}\n")
    
    test_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    print(f"📍 Testando: {test_url}\n")
    
    success, fail = run_youtube_opener(test_url, num_browsers=1, watch_duration=15)
    
    print(f"\n{'='*60}")
    print(f"📊 Resultado: {success} sucesso(s), {fail} falha(s)")
    print(f"{'='*60}")
