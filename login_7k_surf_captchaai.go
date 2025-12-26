//go:build login_surf

package main

import (
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"os"
	"regexp"
	"strings"
	"time"

	"github.com/enetx/g"
	"github.com/enetx/surf"
)

// Configurações CaptchaAI - https://captchaai.com/api-docs.php
const (
	CAPTCHAAI_KEY      = "e2ed228483afe3194f758afd55403e74"
	CAPTCHAAI_IN_URL   = "https://ocr.captchaai.com/in.php"
	CAPTCHAAI_RES_URL  = "https://ocr.captchaai.com/res.php"
	DEFAULT_SITEKEY    = "0x4AAAAAAAykd8yJm3kQzNJc"
	TARGET_URL         = "https://7k.bet.br"
	LOGIN_API          = "https://7k.bet.br/api/auth/login"
	DEFAULT_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

var (
	proxyConfig string
	emailLogin  string
	senhaLogin  string
)

func parseProxyString(proxyStr string) (host, port, user, pass string) {
	parts := strings.Split(proxyStr, "@")
	if len(parts) == 2 {
		userPass := strings.SplitN(parts[0], ":", 2)
		hostPort := strings.Split(parts[1], ":")
		if len(userPass) >= 2 && len(hostPort) >= 2 {
			user = userPass[0]
			pass = userPass[1]
			host = hostPort[0]
			port = hostPort[1]
		}
	}
	return
}

func criarClienteSurf(proxyStr string) *surf.Client {
	host, port, user, pass := parseProxyString(proxyStr)
	proxyURL := fmt.Sprintf("http://%s:%s@%s:%s", user, pass, host, port)

	client := surf.NewClient().
		Builder().
		Proxy(proxyURL).
		UserAgent(DEFAULT_USER_AGENT).
		Build()

	return client
}

func main() {
	fmt.Println("════════════════════════════════════════════════════════════════")
	fmt.Println("     LOGIN 7k.bet.br - SURF + CAPTCHAAI (PASSO A PASSO)")
	fmt.Println("════════════════════════════════════════════════════════════════")

	// Configurações
	if len(os.Args) < 2 {
		proxyConfig = "liderbet1-zone-adam-region-br:Aa10203040@pybpm-ins-hxqlzicm.pyproxy.io:2510"
	} else {
		proxyConfig = os.Args[1]
	}

	emailLogin = "thomasotto58@gmail.com"
	senhaLogin = "Thom@s147"

	host, port, user, _ := parseProxyString(proxyConfig)

	fmt.Println("\n┌─────────────────────────────────────────────────────────────┐")
	fmt.Println("│ CONFIGURAÇÕES                                               │")
	fmt.Println("└─────────────────────────────────────────────────────────────┘")
	fmt.Printf("  📡 Proxy Host: %s\n", host)
	fmt.Printf("  📡 Proxy Port: %s\n", port)
	fmt.Printf("  📡 Proxy User: %s\n", user)
	fmt.Printf("  📧 Email: %s\n", emailLogin)
	fmt.Printf("  🔑 Senha: %s\n", strings.Repeat("*", len(senhaLogin)))
	fmt.Printf("  🌐 Site: %s\n", TARGET_URL)
	fmt.Printf("  🤖 CaptchaAI Key: %s...%s\n", CAPTCHAAI_KEY[:8], CAPTCHAAI_KEY[len(CAPTCHAAI_KEY)-4:])

	// ═══════════════════════════════════════════════════════════════════════
	// PASSO 1: ACESSAR O SITE COM PROXY
	// ═══════════════════════════════════════════════════════════════════════
	fmt.Println("\n┌─────────────────────────────────────────────────────────────┐")
	fmt.Println("│ PASSO 1: ACESSANDO SITE COM PROXY                           │")
	fmt.Println("└─────────────────────────────────────────────────────────────┘")

	fmt.Printf("  → Criando cliente HTTP com proxy...\n")
	client := criarClienteSurf(proxyConfig)
	fmt.Printf("  ✓ Cliente criado com proxy: %s:%s\n", host, port)

	fmt.Printf("  → Fazendo GET em %s...\n", TARGET_URL)
	resp := client.Get(g.String(TARGET_URL)).
		SetHeaders("Accept", "text/html,application/xhtml+xml").
		Do()

	if resp.IsErr() {
		fmt.Printf("  ✗ ERRO ao acessar site: %v\n", resp.Err())
		return
	}

	response := resp.Ok()
	bodyStr := string(response.Body.String())
	fmt.Printf("  ✓ Site acessado com sucesso!\n")
	fmt.Printf("  ✓ Status HTTP: %d\n", response.StatusCode)
	fmt.Printf("  ✓ Tamanho HTML: %d bytes\n", len(bodyStr))

	// Extrair sitekey do JavaScript inline (Nuxt.js SPA)
	fmt.Printf("  → Procurando sitekey do Turnstile no HTML...\n")

	sitekey := ""
	patterns := []string{
		// Formato JavaScript inline do Nuxt.js: turnstileSiteKey:"0x..."
		`turnstileSiteKey["\s]*:["\s]*["']?(0x[0-9a-zA-Z_-]+)["']?`,
		// Formato alternativo: "turnstileSiteKey":"0x..."
		`"turnstileSiteKey"\s*:\s*"(0x[0-9a-zA-Z_-]+)"`,
		// Formato com espaços: turnstileSiteKey : "0x..."
		`turnstileSiteKey\s*:\s*"(0x[0-9a-zA-Z_-]+)"`,
		// Formato HTML tradicional: data-sitekey="0x..."
		`data-sitekey="(0x[0-9a-zA-Z_-]+)"`,
		// Formato cf-turnstile com data-sitekey
		`cf-turnstile[^>]*data-sitekey="(0x[0-9a-zA-Z_-]+)"`,
	}

	for i, pattern := range patterns {
		re := regexp.MustCompile(pattern)
		matches := re.FindStringSubmatch(bodyStr)
		if len(matches) > 1 && strings.HasPrefix(matches[1], "0x") {
			sitekey = matches[1]
			fmt.Printf("  ✓ Sitekey extraído com pattern %d\n", i+1)
			break
		}
	}

	if sitekey == "" {
		fmt.Printf("  ✗ ERRO: Não foi possível extrair sitekey do site!\n")
		fmt.Printf("  → Verifique se o HTML contém 'turnstileSiteKey'\n")
		return
	}
	fmt.Printf("  ✓ SITEKEY EXTRAÍDO DO SITE: %s\n", sitekey)

	// ═══════════════════════════════════════════════════════════════════════
	// PASSO 2: ENVIAR PARA CAPTCHAAI
	// ═══════════════════════════════════════════════════════════════════════
	fmt.Println("\n┌─────────────────────────────────────────────────────────────┐")
	fmt.Println("│ PASSO 2: ENVIANDO TURNSTILE PARA CAPTCHAAI                  │")
	fmt.Println("└─────────────────────────────────────────────────────────────┘")

	fmt.Printf("  → Preparando requisição para CaptchaAI...\n")
	fmt.Printf("    • API: %s\n", CAPTCHAAI_IN_URL)
	fmt.Printf("    • Método: turnstile\n")
	fmt.Printf("    • Sitekey: %s\n", sitekey)
	fmt.Printf("    • PageURL: %s\n", TARGET_URL)

	// Preparar dados conforme documentação: https://captchaai.com/api-docs.php
	data := url.Values{}
	data.Set("key", CAPTCHAAI_KEY)
	data.Set("method", "turnstile")
	data.Set("sitekey", sitekey)
	data.Set("pageurl", TARGET_URL)
	data.Set("json", "1")

	// User-Agent DEVE ser o mesmo usado para acessar o site (match com Cloudflare)
	data.Set("userAgent", DEFAULT_USER_AGENT)
	fmt.Printf("    • UserAgent: %s\n", DEFAULT_USER_AGENT)

	// NOTA: NÃO passamos proxy para CaptchaAI porque:
	// 1. A proxy é rotativa (IP muda a cada requisição)
	// 2. CaptchaAI precisa de IP consistente para resolver
	// 3. O token Turnstile geralmente funciona mesmo com IP diferente
	// Se precisar usar proxy, descomente as linhas abaixo:
	useProxyForCaptcha := os.Getenv("CAPTCHA_USE_PROXY") == "1"
	if useProxyForCaptcha {
		_, _, _, pass := parseProxyString(proxyConfig)
		proxyForAPI := fmt.Sprintf("%s:%s@%s:%s", user, pass, host, port)
		data.Set("proxy", proxyForAPI)
		data.Set("proxytype", "HTTP")
		fmt.Printf("    • Proxy: %s (enviando para CaptchaAI)\n", proxyForAPI)
	} else {
		fmt.Printf("    • Proxy: NÃO ENVIADA (CaptchaAI usará próprio IP)\n")
		fmt.Printf("    • Motivo: Proxy rotativa pode causar ERROR_CAPTCHA_UNSOLVABLE\n")
	}

	httpClient := &http.Client{Timeout: 60 * time.Second}

	fmt.Printf("  → Enviando para CaptchaAI...\n")
	respCaptcha, err := httpClient.PostForm(CAPTCHAAI_IN_URL, data)
	if err != nil {
		fmt.Printf("  ✗ ERRO ao enviar: %v\n", err)
		return
	}
	defer respCaptcha.Body.Close()

	body, _ := io.ReadAll(respCaptcha.Body)
	respStr := string(body)
	fmt.Printf("  ✓ Resposta CaptchaAI: %s\n", respStr)

	// Parse taskID
	var taskID string
	var jsonResp map[string]interface{}
	if err := json.Unmarshal(body, &jsonResp); err == nil {
		status, _ := jsonResp["status"].(float64)
		if status != 1 {
			errMsg := jsonResp["request"]
			fmt.Printf("  ✗ ERRO CaptchaAI: %v\n", errMsg)
			return
		}
		switch v := jsonResp["request"].(type) {
		case string:
			taskID = v
		case float64:
			taskID = fmt.Sprintf("%.0f", v)
		}
	}

	fmt.Printf("  ✓ TASK ID: %s\n", taskID)

	// ═══════════════════════════════════════════════════════════════════════
	// PASSO 3: AGUARDAR RESOLUÇÃO DO CAPTCHA
	// ═══════════════════════════════════════════════════════════════════════
	fmt.Println("\n┌─────────────────────────────────────────────────────────────┐")
	fmt.Println("│ PASSO 3: AGUARDANDO CAPTCHAAI RESOLVER                      │")
	fmt.Println("└─────────────────────────────────────────────────────────────┘")

	fmt.Printf("  → Aguardando 20 segundos inicial (recomendado pela doc)...\n")
	time.Sleep(20 * time.Second)

	var captchaToken string
	for i := 0; i < 30; i++ {
		resURL := fmt.Sprintf("%s?key=%s&action=get&id=%s&json=1",
			CAPTCHAAI_RES_URL, CAPTCHAAI_KEY, taskID)

		respRes, err := httpClient.Get(resURL)
		if err != nil {
			fmt.Printf("  [%ds] ERRO: %v\n", 20+(i+1)*5, err)
			time.Sleep(5 * time.Second)
			continue
		}

		bodyRes, _ := io.ReadAll(respRes.Body)
		respRes.Body.Close()
		respResStr := string(bodyRes)

		var resJson map[string]interface{}
		json.Unmarshal(bodyRes, &resJson)

		status, _ := resJson["status"].(float64)
		request, _ := resJson["request"].(string)

		if status == 1 && request != "" && request != "CAPCHA_NOT_READY" {
			captchaToken = request
			fmt.Printf("  [%ds] ✓ RESOLVIDO!\n", 20+(i+1)*5)
			break
		}

		if status == 0 && request != "CAPCHA_NOT_READY" {
			fmt.Printf("  [%ds] ✗ ERRO: %s\n", 20+(i+1)*5, request)
			return
		}

		fmt.Printf("  [%ds] Aguardando... (%s)\n", 20+(i+1)*5, respResStr)
		time.Sleep(5 * time.Second)
	}

	if captchaToken == "" {
		fmt.Println("  ✗ TIMEOUT: Captcha não foi resolvido")
		return
	}

	// ═══════════════════════════════════════════════════════════════════════
	// PASSO 4: MOSTRAR TOKEN RESOLVIDO
	// ═══════════════════════════════════════════════════════════════════════
	fmt.Println("\n┌─────────────────────────────────────────────────────────────┐")
	fmt.Println("│ PASSO 4: TOKEN RESOLVIDO                                    │")
	fmt.Println("└─────────────────────────────────────────────────────────────┘")
	fmt.Printf("  TOKEN COMPLETO:\n")
	fmt.Printf("  ════════════════════════════════════════════════════════════\n")
	fmt.Printf("  %s\n", captchaToken)
	fmt.Printf("  ════════════════════════════════════════════════════════════\n")
	fmt.Printf("  Tamanho do token: %d caracteres\n", len(captchaToken))

	// ═══════════════════════════════════════════════════════════════════════
	// PASSO 5: FAZER LOGIN COM TOKEN
	// ═══════════════════════════════════════════════════════════════════════
	fmt.Println("\n┌─────────────────────────────────────────────────────────────┐")
	fmt.Println("│ PASSO 5: FAZENDO LOGIN COM TOKEN                            │")
	fmt.Println("└─────────────────────────────────────────────────────────────┘")

	fmt.Printf("  → Preparando payload de login...\n")
	payload := map[string]string{
		"login":         emailLogin,
		"password":      senhaLogin,
		"captcha_token": captchaToken,
	}

	payloadJSON, _ := json.Marshal(payload)
	fmt.Printf("    • Email: %s\n", emailLogin)
	fmt.Printf("    • Senha: %s\n", strings.Repeat("*", len(senhaLogin)))
	fmt.Printf("    • Token: %s...\n", captchaToken[:min(40, len(captchaToken))])
	fmt.Printf("    • API: %s\n", LOGIN_API)

	fmt.Printf("  → Enviando POST para login (usando mesmo proxy)...\n")

	respLogin := client.Post(g.String(LOGIN_API), payload).
		SetHeaders(
			"Content-Type", "application/json",
			"Accept", "application/json",
			"Origin", "https://7k.bet.br",
			"Referer", "https://7k.bet.br/",
		).
		Do()

	if respLogin.IsErr() {
		fmt.Printf("  ✗ ERRO no login: %v\n", respLogin.Err())
		return
	}

	resultLogin := respLogin.Ok()
	bodyLogin := string(resultLogin.Body.String())

	fmt.Printf("  ✓ Status HTTP: %d\n", resultLogin.StatusCode)
	fmt.Printf("  ✓ Resposta:\n")
	fmt.Printf("  ════════════════════════════════════════════════════════════\n")
	fmt.Printf("  %s\n", bodyLogin)
	fmt.Printf("  ════════════════════════════════════════════════════════════\n")

	// Parse resposta
	var loginResp map[string]interface{}
	if err := json.Unmarshal([]byte(bodyLogin), &loginResp); err == nil {
		if resultLogin.StatusCode == 200 {
			fmt.Println("\n  🎉🎉🎉 LOGIN BEM SUCEDIDO! 🎉🎉🎉")
			if token, ok := loginResp["token"].(string); ok {
				fmt.Printf("  JWT Token: %s...\n", token[:min(50, len(token))])
			}
		} else {
			fmt.Printf("\n  ❌ Login falhou: %v\n", loginResp)
		}
	}

	fmt.Println("\n════════════════════════════════════════════════════════════════")
	fmt.Println("     PROCESSO FINALIZADO")
	fmt.Println("════════════════════════════════════════════════════════════════")

	// Descartar variável não usada
	_ = payloadJSON
}

func min(a, b int) int {
	if a < b {
		return a
	}
	return b
}
