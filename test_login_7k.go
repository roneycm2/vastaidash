package main

import (
	"bytes"
	"crypto/tls"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"time"
)

// Configuração do Proxy
const (
	PROXY_HOST = "pybpm-ins-hxqlzicm.pyproxy.io"
	PROXY_PORT = "2510"
	PROXY_USER = "liderbet1-zone-adam-region-br"
	PROXY_PASS = "Aa10203040"
)

// Credenciais
const (
	EMAIL = "thomasotto58@gmail.com"
	SENHA = "Thom@s147"
)

// Estruturas para JSON
type LoginRequest struct {
	Email        string `json:"email"`
	Password     string `json:"password"`
	CaptchaToken string `json:"captcha_token"`
}

type LoginRequestUsername struct {
	Username     string `json:"username"`
	Password     string `json:"password"`
	CaptchaToken string `json:"captcha_token"`
}

type LoginResponse struct {
	Success bool                   `json:"success,omitempty"`
	Message string                 `json:"message,omitempty"`
	Error   string                 `json:"error,omitempty"`
	Data    map[string]interface{} `json:"data,omitempty"`
	Token   string                 `json:"token,omitempty"`
	User    map[string]interface{} `json:"user,omitempty"`
}

func criarClienteComProxy() *http.Client {
	// Configura proxy URL
	proxyURL, err := url.Parse(fmt.Sprintf("http://%s:%s@%s:%s", PROXY_USER, PROXY_PASS, PROXY_HOST, PROXY_PORT))
	if err != nil {
		fmt.Printf("❌ Erro ao parsear proxy URL: %v\n", err)
		return nil
	}

	// Configura transporte com proxy
	transport := &http.Transport{
		Proxy: http.ProxyURL(proxyURL),
		TLSClientConfig: &tls.Config{
			InsecureSkipVerify: true,
		},
	}

	// Cria cliente HTTP
	client := &http.Client{
		Transport: transport,
		Timeout:   30 * time.Second,
	}

	return client
}

func verificarIP(client *http.Client) string {
	fmt.Println("\n[1] Verificando IP via proxy...")

	resp, err := client.Get("https://api.ipify.org?format=json")
	if err != nil {
		fmt.Printf("    ❌ Erro: %v\n", err)
		return ""
	}
	defer resp.Body.Close()

	body, _ := io.ReadAll(resp.Body)
	var result map[string]string
	json.Unmarshal(body, &result)

	ip := result["ip"]
	fmt.Printf("    ✅ IP: %s\n", ip)
	return ip
}

func acessarSite(client *http.Client) []*http.Cookie {
	fmt.Println("\n[2] Acessando 7k.bet.br para obter cookies...")

	req, _ := http.NewRequest("GET", "https://7k.bet.br", nil)
	req.Header.Set("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
	req.Header.Set("Accept", "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8")
	req.Header.Set("Accept-Language", "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7")

	resp, err := client.Do(req)
	if err != nil {
		fmt.Printf("    ❌ Erro: %v\n", err)
		return nil
	}
	defer resp.Body.Close()

	fmt.Printf("    Status: %d\n", resp.StatusCode)
	fmt.Printf("    Cookies: %d\n", len(resp.Cookies()))

	for _, cookie := range resp.Cookies() {
		fmt.Printf("      - %s: %s...\n", cookie.Name, cookie.Value[:min(20, len(cookie.Value))])
	}

	return resp.Cookies()
}

func tentarLogin(client *http.Client, endpoint string, payload interface{}, cookies []*http.Cookie) {
	fmt.Printf("\n    Endpoint: %s\n", endpoint)

	jsonData, _ := json.Marshal(payload)

	req, _ := http.NewRequest("POST", endpoint, bytes.NewBuffer(jsonData))
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Accept", "application/json")
	req.Header.Set("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
	req.Header.Set("Origin", "https://7k.bet.br")
	req.Header.Set("Referer", "https://7k.bet.br/")

	// Adiciona cookies
	for _, cookie := range cookies {
		req.AddCookie(cookie)
	}

	resp, err := client.Do(req)
	if err != nil {
		fmt.Printf("    ❌ Erro: %v\n", err)
		return
	}
	defer resp.Body.Close()

	body, _ := io.ReadAll(resp.Body)

	fmt.Printf("    Status: %d\n", resp.StatusCode)
	fmt.Printf("    Resposta: %s\n", truncate(string(body), 500))

	// Tenta parsear como JSON
	var loginResp LoginResponse
	if err := json.Unmarshal(body, &loginResp); err == nil {
		if loginResp.Success || loginResp.Token != "" {
			fmt.Println("\n    🎉 LOGIN BEM SUCEDIDO!")
		} else if loginResp.Error != "" || loginResp.Message != "" {
			fmt.Printf("    ⚠️ Mensagem: %s %s\n", loginResp.Message, loginResp.Error)
		}
	}
}

func truncate(s string, max int) string {
	if len(s) <= max {
		return s
	}
	return s[:max] + "..."
}

func min(a, b int) int {
	if a < b {
		return a
	}
	return b
}

func main() {
	fmt.Println("============================================================")
	fmt.Println("[LOGIN 7k.bet.br - Go + HTTP Client com Proxy]")
	fmt.Println("============================================================")
	fmt.Printf("Email: %s\n", EMAIL)
	fmt.Printf("Senha: %s\n", "********")
	fmt.Println("============================================================")

	// Cria cliente com proxy
	client := criarClienteComProxy()
	if client == nil {
		return
	}

	// Verifica IP
	ip := verificarIP(client)
	if ip == "" {
		fmt.Println("❌ Proxy não funcionando. Abortando.")
		return
	}

	// Acessa o site para cookies
	cookies := acessarSite(client)

	// Testa diferentes endpoints e payloads
	fmt.Println("\n[3] Testando endpoints de login...")

	endpoints := []string{
		"https://7k.bet.br/api/auth/login",
		"https://7k.bet.br/api/login",
		"https://7k.bet.br/api/v1/auth/login",
		"https://7k.bet.br/api/sessions",
	}

	// Payload 1: email + password
	payload1 := LoginRequest{
		Email:        EMAIL,
		Password:     SENHA,
		CaptchaToken: "",
	}

	// Payload 2: username + password
	payload2 := LoginRequestUsername{
		Username:     EMAIL,
		Password:     SENHA,
		CaptchaToken: "",
	}

	for _, endpoint := range endpoints {
		fmt.Println("\n    ---")
		tentarLogin(client, endpoint, payload1, cookies)
	}

	// Tenta com username
	fmt.Println("\n[4] Testando com 'username' ao invés de 'email'...")
	tentarLogin(client, "https://7k.bet.br/api/auth/login", payload2, cookies)

	// Tenta outros formatos de payload
	fmt.Println("\n[5] Testando outros formatos de payload...")

	// Formato 3: identifier
	payload3 := map[string]string{
		"identifier":    EMAIL,
		"password":      SENHA,
		"captcha_token": "",
	}
	tentarLogin(client, "https://7k.bet.br/api/auth/login", payload3, cookies)

	// Formato 4: login
	payload4 := map[string]string{
		"login":    EMAIL,
		"password": SENHA,
	}
	tentarLogin(client, "https://7k.bet.br/api/auth/login", payload4, cookies)

	// Formato 5: document (CPF)
	payload5 := map[string]string{
		"document":      EMAIL,
		"password":      SENHA,
		"captcha_token": "",
	}
	tentarLogin(client, "https://7k.bet.br/api/auth/login", payload5, cookies)

	fmt.Println("\n============================================================")
	fmt.Println("[FIM DO TESTE]")
	fmt.Println("============================================================")
}

