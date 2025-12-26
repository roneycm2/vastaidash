# 🛡️ Guia de Bypass do Cloudflare - 7k.bet.br

## 📊 Análise dos Cookies do Cloudflare

### Cookies Detectados:
| Cookie | Função | Duração | Dificuldade |
|--------|--------|---------|-------------|
| `__cf_bm` | **Bot Management** - Identifica tráfego automatizado | 30 min | 🔴 Alta |
| `_cfuvid` | **Unique Visitor ID** - Rastreia visitante único | Sessão | 🟡 Média |
| `cf_clearance` | **Clearance** - Prova que passou no challenge | 15-30 min | 🔴 Alta |

### Como o Cloudflare Detecta Bots:

1. **TLS Fingerprinting** - Analisa a "impressão digital" da conexão SSL/TLS
2. **Browser Fingerprinting** - Verifica propriedades do navegador (navigator, screen, etc.)
3. **Behavioral Analysis** - Analisa padrões de movimento do mouse e cliques
4. **Rate Limiting** - Limita requisições por IP/sessão (~12-15 req antes de bloquear)
5. **JavaScript Challenge** - Executa código JS para verificar ambiente real

---

## 🔧 Alternativas para Bypass

### 1. **curl_cffi** (TLS Fingerprint Impersonation)
Melhor para requisições de API simples.

```python
# pip install curl_cffi
from curl_cffi import requests

session = requests.Session(impersonate="chrome120")
response = session.get("https://7k.bet.br/")
```

### 2. **Patchright/Playwright** (Seu método atual)
Melhor para desafios visuais/Turnstile. Você já tem isso implementado!

### 3. **undetected-chromedriver**
Alternativa ao Selenium com patches anti-detecção.

```python
# pip install undetected-chromedriver
import undetected_chromedriver as uc
driver = uc.Chrome()
driver.get("https://7k.bet.br/")
```

### 4. **Serviços de Resolução (Pago)**
- 2Captcha, Anti-Captcha, CapSolver
- Custo: ~$2-3 por 1000 resoluções

---

## 🚀 Solução Recomendada: Híbrida

Combina Patchright para obter cookies válidos + curl_cffi para requisições rápidas.


