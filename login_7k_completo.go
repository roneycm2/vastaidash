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

/*
Login 7k.bet.br - Versão Completa
1. Resolve Turnstile via Anti-Captcha
2. Faz login via API com o token

Se falhar por Cloudflare, recomenda-se usar navegador.
*/

const (
	ANTICAPTCHA_KEY = "f80abc2cefe60bfec5c97f16294a1452"
	PROXY_HOST      = "pybpm-ins-hxqlzicm.pyproxy.io"
	PROXY_PORT      = "2510"
	PROXY_USER      = "liderbet1-zone-adam-region-br"
	PROXY_PASS      = "Aa10203040"
	
	TURNSTILE_SITEKEY = "0x4AAAAAAAykd8yJm3kQzNJc"
	
	EMAIL = "thomasotto58@gmail.com"
	SENHA = "Thom@s147"
)

type CreateTaskRequest struct {
	ClientKey string      `json:"clientKey"`
	Task      interface{} `json:"task"`
}

type TurnstileTask struct {
	Type       string `json:"type"`
	WebsiteURL string `json:"websiteURL"`
	WebsiteKey string `json:"websiteKey"`
}

type CreateTaskResponse struct {
	ErrorId   int    `json:"errorId"`
	ErrorCode string `json:"errorCode"`
	TaskId    int    `json:"taskId"`
}

type GetResultRequest struct {
	ClientKey string `json:"clientKey"`
	TaskId    int    `json:"taskId"`
}

type GetResultResponse struct {
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

func resolverTurnstile() (string, error) {
	fmt.Println("\n[1] RESOLVENDO TURNSTILE...")
	fmt.Printf("    SiteKey: %s\n", TURNSTILE_SITEKEY)
	
	client := &http.Client{Timeout: 120 * time.Second}
	
	// Criar tarefa
	taskReq := CreateTaskRequest{
		ClientKey: ANTICAPTCHA_KEY,
		Task: TurnstileTask{
			Type:       "TurnstileTaskProxyless",
			WebsiteURL: "https://7k.bet.br",
			WebsiteKey: TURNSTILE_SITEKEY,
		},
	}
	
	jsonData, _ := json.Marshal(taskReq)
	resp, err := client.Post("https://api.anti-captcha.com/createTask", "application/json", bytes.NewBuffer(jsonData))
	if err != nil {
		return "", err
	}
	defer resp.Body.Close()
	
	body, _ := io.ReadAll(resp.Body)
	var taskResp CreateTaskResponse
	json.Unmarshal(body, &taskResp)
	
	if taskResp.ErrorId != 0 {
		return "", fmt.Errorf("Anti-Captcha erro: %s", taskResp.ErrorCode)
	}
	
	fmt.Printf("    TaskId: %d\n", taskResp.TaskId)
	fmt.Println("    Aguardando resolução...")
	
	// Aguardar resultado
	getResultReq := GetResultRequest{
		ClientKey: ANTICAPTCHA_KEY,
		TaskId:    taskResp.TaskId,
	}
	
	for i := 0; i < 40; i++ {
		time.Sleep(3 * time.Second)
		fmt.Printf("    Verificando... %ds\n", (i+1)*3)
		
		jsonData, _ := json.Marshal(getResultReq)
		resp, err := client.Post("https://api.anti-captcha.com/getTaskResult", "application/json", bytes.NewBuffer(jsonData))
		if err != nil {
			continue
		}
		
		body, _ := io.ReadAll(resp.Body)
		resp.Body.Close()
		
		var result GetResultResponse
		json.Unmarshal(body, &result)
		
		if result.Status == "ready" {
			fmt.Println("    ✅ TOKEN OBTIDO!")
			return result.Solution.Token, nil
		}
	}
	
	return "", fmt.Errorf("timeout")
}

func fazerLogin(token string) {
	fmt.Println("\n[2] FAZENDO LOGIN...")
	fmt.Printf("    Email: %s\n", EMAIL)
	
	client := criarClienteComProxy()
	
	// Primeiro pega cookies do site
	fmt.Println("    Acessando site para cookies...")
	
	jar, _ := (&http.Client{}).Get("https://7k.bet.br")
	if jar != nil {
		jar.Body.Close()
	}
	
	// Faz login
	payload := map[string]string{
		"login":         EMAIL,
		"password":      SENHA,
		"captcha_token": token,
	}
	
	jsonData, _ := json.Marshal(payload)
	
	req, _ := http.NewRequest("POST", "https://7k.bet.br/api/auth/login", bytes.NewBuffer(jsonData))
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Accept", "application/json")
	req.Header.Set("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
	req.Header.Set("Origin", "https://7k.bet.br")
	req.Header.Set("Referer", "https://7k.bet.br/")
	
	fmt.Println("    Enviando requisição de login...")
	
	resp, err := client.Do(req)
	if err != nil {
		fmt.Printf("    ❌ Erro: %v\n", err)
		fmt.Println("\n    ⚠️ O Cloudflare está bloqueando requisições HTTP diretas.")
		fmt.Println("    Use o navegador (Playwright) para fazer o login.")
		return
	}
	defer resp.Body.Close()
	
	body, _ := io.ReadAll(resp.Body)
	
	fmt.Printf("\n    Status: %d\n", resp.StatusCode)
	fmt.Printf("    Resposta: %s\n", string(body))
	
	if resp.StatusCode == 200 {
		fmt.Println("\n    🎉 LOGIN BEM SUCEDIDO!")
	} else {
		fmt.Println("\n    ⚠️ Login falhou - verifique a resposta acima")
	}
}

func main() {
	fmt.Println("============================================================")
	fmt.Println("LOGIN 7k.bet.br - Turnstile + Anti-Captcha")
	fmt.Println("============================================================")
	
	// 1. Resolver Turnstile
	token, err := resolverTurnstile()
	if err != nil {
		fmt.Printf("\n❌ Erro ao resolver Turnstile: %v\n", err)
		return
	}
	
	fmt.Printf("\n    Token (primeiros 80 chars): %s...\n", token[:80])
	
	// 2. Fazer login
	fazerLogin(token)
	
	fmt.Println("\n============================================================")
	fmt.Println("FIM")
	fmt.Println("============================================================")
}











