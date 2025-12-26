package main

import (
	"crypto/tls"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"regexp"
	"strings"
	"time"
)

// Configuração do Proxy
const (
	PROXY_HOST = "pybpm-ins-hxqlzicm.pyproxy.io"
	PROXY_PORT = "2510"
	PROXY_USER = "liderbet1-zone-adam-region-br"
	PROXY_PASS = "Aa10203040"
)

func criarClienteComProxy() *http.Client {
	proxyURL, _ := url.Parse(fmt.Sprintf("http://%s:%s@%s:%s", PROXY_USER, PROXY_PASS, PROXY_HOST, PROXY_PORT))

	transport := &http.Transport{
		Proxy: http.ProxyURL(proxyURL),
		TLSClientConfig: &tls.Config{
			InsecureSkipVerify: true,
		},
	}

	return &http.Client{
		Transport: transport,
		Timeout:   30 * time.Second,
	}
}

func buscarTurnstileInfo(client *http.Client, pageURL string) {
	fmt.Printf("\n[Buscando Turnstile em: %s]\n", pageURL)

	req, _ := http.NewRequest("GET", pageURL, nil)
	req.Header.Set("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
	req.Header.Set("Accept", "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8")
	req.Header.Set("Accept-Language", "pt-BR,pt;q=0.9,en;q=0.8")

	resp, err := client.Do(req)
	if err != nil {
		fmt.Printf("❌ Erro: %v\n", err)
		return
	}
	defer resp.Body.Close()

	body, _ := io.ReadAll(resp.Body)
	html := string(body)

	fmt.Printf("Status: %d\n", resp.StatusCode)
	fmt.Printf("Tamanho HTML: %d bytes\n", len(html))

	// Padrões para encontrar Turnstile
	patterns := []struct {
		name    string
		pattern string
	}{
		{"Turnstile sitekey (data-sitekey)", `data-sitekey="([^"]+)"`},
		{"Turnstile sitekey (sitekey:)", `sitekey['":\s]+['"]([0-9a-zA-Z_-]+)['"]`},
		{"Turnstile widget", `cf-turnstile[^>]*data-sitekey="([^"]+)"`},
		{"Cloudflare challenges", `challenges\.cloudflare\.com[^"]*`},
		{"Turnstile script", `turnstile[^"]*\.js`},
		{"reCAPTCHA sitekey", `data-sitekey="([^"]+)"`},
		{"reCAPTCHA v3", `grecaptcha\.execute\(['"]([^'"]+)['"]`},
		{"hCaptcha sitekey", `data-sitekey="([^"]+)"`},
		{"Captcha container", `(captcha|recaptcha|hcaptcha|turnstile)[^>]*>`},
	}

	fmt.Println("\n[Resultados da busca]")
	fmt.Println(strings.Repeat("-", 60))

	foundAny := false
	for _, p := range patterns {
		re := regexp.MustCompile(p.pattern)
		matches := re.FindAllStringSubmatch(html, -1)
		if len(matches) > 0 {
			foundAny = true
			fmt.Printf("\n✅ %s:\n", p.name)
			for _, match := range matches {
				if len(match) > 1 {
					fmt.Printf("   → %s\n", match[1])
				} else {
					fmt.Printf("   → %s\n", match[0])
				}
			}
		}
	}

	// Busca específica por Cloudflare Turnstile
	if strings.Contains(html, "turnstile") || strings.Contains(html, "cf-turnstile") {
		fmt.Println("\n🔵 CLOUDFLARE TURNSTILE DETECTADO!")

		// Extrai o sitekey
		re := regexp.MustCompile(`cf-turnstile[^>]*data-sitekey="([^"]+)"`)
		if match := re.FindStringSubmatch(html); len(match) > 1 {
			fmt.Printf("   SITEKEY: %s\n", match[1])
		}

		// Busca em scripts inline
		re2 := regexp.MustCompile(`turnstile\.render\([^)]*sitekey['":\s]+['"]([^'"]+)['"]`)
		if match := re2.FindStringSubmatch(html); len(match) > 1 {
			fmt.Printf("   SITEKEY (render): %s\n", match[1])
		}
	}

	// Busca por reCAPTCHA
	if strings.Contains(html, "recaptcha") || strings.Contains(html, "grecaptcha") {
		fmt.Println("\n🟢 GOOGLE reCAPTCHA DETECTADO!")
		re := regexp.MustCompile(`data-sitekey="([^"]+)"`)
		if match := re.FindStringSubmatch(html); len(match) > 1 {
			fmt.Printf("   SITEKEY: %s\n", match[1])
		}
	}

	// Busca por hCaptcha
	if strings.Contains(html, "hcaptcha") {
		fmt.Println("\n🟡 hCAPTCHA DETECTADO!")
		re := regexp.MustCompile(`data-sitekey="([^"]+)"`)
		if match := re.FindStringSubmatch(html); len(match) > 1 {
			fmt.Printf("   SITEKEY: %s\n", match[1])
		}
	}

	if !foundAny {
		fmt.Println("\n⚠️ Nenhum captcha encontrado no HTML estático.")
		fmt.Println("   O captcha pode ser carregado dinamicamente via JavaScript.")
		fmt.Println("   Pode ser necessário usar um navegador para extrair o sitekey.")
	}

	// Mostra um trecho do HTML onde pode ter captcha
	fmt.Println("\n[Trechos relevantes do HTML]")
	fmt.Println(strings.Repeat("-", 60))

	keywords := []string{"captcha", "turnstile", "recaptcha", "hcaptcha", "sitekey", "challenge"}
	for _, kw := range keywords {
		idx := strings.Index(strings.ToLower(html), kw)
		if idx != -1 {
			start := max(0, idx-100)
			end := min(len(html), idx+200)
			snippet := html[start:end]
			snippet = strings.ReplaceAll(snippet, "\n", " ")
			snippet = strings.ReplaceAll(snippet, "\r", "")
			fmt.Printf("\n📍 '%s' encontrado:\n   ...%s...\n", kw, snippet)
		}
	}
}

func max(a, b int) int {
	if a > b {
		return a
	}
	return b
}

func min(a, b int) int {
	if a < b {
		return a
	}
	return b
}

func main() {
	fmt.Println("============================================================")
	fmt.Println("[BUSCA CLOUDFLARE TURNSTILE - 7k.bet.br]")
	fmt.Println("============================================================")

	client := criarClienteComProxy()

	// Busca na página principal
	buscarTurnstileInfo(client, "https://7k.bet.br")

	// Busca na página de login (se existir)
	fmt.Println("\n" + strings.Repeat("=", 60))
	buscarTurnstileInfo(client, "https://7k.bet.br/login")

	// Busca na página de registro
	fmt.Println("\n" + strings.Repeat("=", 60))
	buscarTurnstileInfo(client, "https://7k.bet.br/register")

	fmt.Println("\n============================================================")
	fmt.Println("[FIM]")
	fmt.Println("============================================================")
}

