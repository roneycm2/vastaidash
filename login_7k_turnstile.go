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

// Credenciais 7k.bet.br
const (
	EMAIL = "thomasotto58@gmail.com"
	SENHA = "Thom@s147"
)

// Cloudflare Turnstile
const (
	TURNSTILE_SITEKEY = "0x4AAAAAAAykd8yJm3kQzNJc"
	PAGE_URL          = "https://7k.bet.br"
)

// API Key do Anti-Captcha (você já tem no projeto)
const ANTICAPTCHA_KEY = "f80abc2cefe60bfec5c97f16294a1452"

// Estruturas
type AntiCaptchaTask struct {
	ClientKey string      `json:"clientKey"`
	Task      interface{} `json:"task"`
}

type TurnstileTask struct {
	Type       string `json:"type"`
	WebsiteURL string `json:"websiteURL"`
	WebsiteKey string `json:"websiteKey"`
}

type TaskResponse struct {
	ErrorId   int    `json:"errorId"`
	ErrorCode string `json:"errorCode"`
	TaskId    int    `json:"taskId"`
}

type GetResultRequest struct {
	ClientKey string `json:"clientKey"`
	TaskId    int    `json:"taskId"`
}

type TaskResult struct {
	ErrorId  int    `json:"errorId"`
	Status   string `json:"status"`
	Solution struct {
		Token string `json:"token"`
	} `json:"solution"`
}

func criarClienteComProxy() *http.Client {
	proxyURL, _ := url.Parse(fmt.Sprintf("http://%s:%s@%s:%s", PROXY_USER, PROXY_PASS, PROXY_HOST, PROXY_PORT))
	transport := &http.Transport{
		Proxy:           http.ProxyURL(proxyURL),
		TLSClientConfig: &tls.Config{InsecureSkipVerify: true},
	}
	return &http.Client{Transport: transport, Timeout: 60 * time.Second}
}

func criarClienteSemProxy() *http.Client {
	return &http.Client{Timeout: 60 * time.Second}
}

func resolverTurnstile() (string, error) {
	fmt.Println("\n[RESOLVENDO CLOUDFLARE TURNSTILE]")
	fmt.Printf("SiteKey: %s\n", TURNSTILE_SITEKEY)
	fmt.Printf("URL: %s\n", PAGE_URL)

	client := criarClienteSemProxy() // Anti-Captcha não precisa de proxy

	// 1. Criar tarefa
	fmt.Println("\n[1] Criando tarefa no Anti-Captcha...")

	task := AntiCaptchaTask{
		ClientKey: ANTICAPTCHA_KEY,
		Task: TurnstileTask{
			Type:       "TurnstileTaskProxyless",
			WebsiteURL: PAGE_URL,
			WebsiteKey: TURNSTILE_SITEKEY,
		},
	}

	jsonData, _ := json.Marshal(task)
	resp, err := client.Post("https://api.anti-captcha.com/createTask", "application/json", bytes.NewBuffer(jsonData))
	if err != nil {
		return "", fmt.Errorf("erro ao criar tarefa: %v", err)
	}
	defer resp.Body.Close()

	body, _ := io.ReadAll(resp.Body)
	var taskResp TaskResponse
	json.Unmarshal(body, &taskResp)

	if taskResp.ErrorId != 0 {
		return "", fmt.Errorf("erro Anti-Captcha: %s", taskResp.ErrorCode)
	}

	fmt.Printf("    TaskId: %d\n", taskResp.TaskId)

	// 2. Aguardar resolução
	fmt.Println("\n[2] Aguardando resolução (pode levar 10-60s)...")

	getResult := GetResultRequest{
		ClientKey: ANTICAPTCHA_KEY,
		TaskId:    taskResp.TaskId,
	}

	for i := 0; i < 60; i++ {
		time.Sleep(3 * time.Second)
		fmt.Printf("    Verificando... (%ds)\n", (i+1)*3)

		jsonData, _ := json.Marshal(getResult)
		resp, err := client.Post("https://api.anti-captcha.com/getTaskResult", "application/json", bytes.NewBuffer(jsonData))
		if err != nil {
			continue
		}

		body, _ := io.ReadAll(resp.Body)
		resp.Body.Close()

		var result TaskResult
		json.Unmarshal(body, &result)

		if result.Status == "ready" {
			fmt.Println("\n✅ CAPTCHA RESOLVIDO!")
			fmt.Printf("    Token: %s...\n", result.Solution.Token[:50])
			return result.Solution.Token, nil
		}
	}

	return "", fmt.Errorf("timeout ao resolver captcha")
}

func fazerLogin(captchaToken string) {
	fmt.Println("\n[FAZENDO LOGIN]")

	client := criarClienteComProxy()

	payload := map[string]string{
		"login":         EMAIL,
		"password":      SENHA,
		"captcha_token": captchaToken,
	}

	jsonData, _ := json.Marshal(payload)

	req, _ := http.NewRequest("POST", "https://7k.bet.br/api/auth/login", bytes.NewBuffer(jsonData))
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Accept", "application/json")
	req.Header.Set("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
	req.Header.Set("Origin", "https://7k.bet.br")
	req.Header.Set("Referer", "https://7k.bet.br/")

	fmt.Println("Enviando requisição de login...")

	resp, err := client.Do(req)
	if err != nil {
		fmt.Printf("❌ Erro: %v\n", err)
		return
	}
	defer resp.Body.Close()

	body, _ := io.ReadAll(resp.Body)

	fmt.Printf("\nStatus: %d\n", resp.StatusCode)
	fmt.Printf("Resposta: %s\n", string(body))

	if resp.StatusCode == 200 {
		fmt.Println("\n🎉 LOGIN BEM SUCEDIDO!")

		// Mostra cookies de sessão
		fmt.Println("\nCookies recebidos:")
		for _, cookie := range resp.Cookies() {
			fmt.Printf("  - %s: %s\n", cookie.Name, cookie.Value[:min(30, len(cookie.Value))]+"...")
		}
	} else {
		fmt.Println("\n❌ LOGIN FALHOU")
	}
}

func min(a, b int) int {
	if a < b {
		return a
	}
	return b
}

func main() {
	fmt.Println("============================================================")
	fmt.Println("[LOGIN 7k.bet.br - Cloudflare Turnstile + Anti-Captcha]")
	fmt.Println("============================================================")
	fmt.Printf("Email: %s\n", EMAIL)
	fmt.Printf("Turnstile SiteKey: %s\n", TURNSTILE_SITEKEY)
	fmt.Println("============================================================")

	// 1. Resolver Turnstile
	token, err := resolverTurnstile()
	if err != nil {
		fmt.Printf("\n❌ Erro ao resolver captcha: %v\n", err)
		return
	}

	// 2. Fazer login com o token
	fazerLogin(token)

	fmt.Println("\n============================================================")
	fmt.Println("[FIM]")
	fmt.Println("============================================================")
}

