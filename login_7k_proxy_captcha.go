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

const (
	ANTICAPTCHA_KEY   = "f80abc2cefe60bfec5c97f16294a1452"
	TURNSTILE_SITEKEY = "0x4AAAAAAAykd8yJm3kQzNJc"
	PROXY_HOST        = "pybpm-ins-hxqlzicm.pyproxy.io"
	PROXY_PORT        = "2510"
	PROXY_USER        = "liderbet1-zone-adam-region-br"
	PROXY_PASS        = "Aa10203040"
	EMAIL             = "thomasotto58@gmail.com"
	SENHA             = "Thom@s147"
)

type CreateTaskRequest struct {
	ClientKey string      `json:"clientKey"`
	Task      interface{} `json:"task"`
}

// TurnstileTask COM proxy - para que o captcha seja resolvido do mesmo IP
type TurnstileTaskWithProxy struct {
	Type          string `json:"type"`
	WebsiteURL    string `json:"websiteURL"`
	WebsiteKey    string `json:"websiteKey"`
	ProxyType     string `json:"proxyType"`
	ProxyAddress  string `json:"proxyAddress"`
	ProxyPort     int    `json:"proxyPort"`
	ProxyLogin    string `json:"proxyLogin"`
	ProxyPassword string `json:"proxyPassword"`
}

type CreateTaskResponse struct {
	ErrorId          int    `json:"errorId"`
	ErrorCode        string `json:"errorCode"`
	ErrorDescription string `json:"errorDescription"`
	TaskId           int    `json:"taskId"`
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
	return &http.Client{Transport: transport, Timeout: 30 * time.Second}
}

func resolverTurnstileComProxy() (string, error) {
	fmt.Println("\n[1] RESOLVENDO TURNSTILE COM PROXY")
	fmt.Printf("    SiteKey: %s\n", TURNSTILE_SITEKEY)
	fmt.Printf("    Proxy: %s:%s\n", PROXY_HOST, PROXY_PORT)

	client := &http.Client{Timeout: 180 * time.Second}

	// Usar TurnstileTask (com proxy) ao invés de TurnstileTaskProxyless
	taskReq := CreateTaskRequest{
		ClientKey: ANTICAPTCHA_KEY,
		Task: TurnstileTaskWithProxy{
			Type:          "TurnstileTask",
			WebsiteURL:    "https://7k.bet.br",
			WebsiteKey:    TURNSTILE_SITEKEY,
			ProxyType:     "http",
			ProxyAddress:  PROXY_HOST,
			ProxyPort:     2510,
			ProxyLogin:    PROXY_USER,
			ProxyPassword: PROXY_PASS,
		},
	}

	jsonData, _ := json.Marshal(taskReq)
	fmt.Printf("    Payload: %s\n", string(jsonData)[:200])

	resp, err := client.Post("https://api.anti-captcha.com/createTask", "application/json", bytes.NewBuffer(jsonData))
	if err != nil {
		return "", err
	}
	defer resp.Body.Close()

	body, _ := io.ReadAll(resp.Body)
	var taskResp CreateTaskResponse
	json.Unmarshal(body, &taskResp)

	if taskResp.ErrorId != 0 {
		return "", fmt.Errorf("Erro %s: %s", taskResp.ErrorCode, taskResp.ErrorDescription)
	}

	fmt.Printf("    TaskId: %d\n", taskResp.TaskId)
	fmt.Println("    Aguardando resolução (pode demorar mais com proxy)...")

	getResultReq := GetResultRequest{ClientKey: ANTICAPTCHA_KEY, TaskId: taskResp.TaskId}

	for i := 0; i < 60; i++ {
		time.Sleep(3 * time.Second)
		fmt.Printf("    Verificando... %ds\r", (i+1)*3)

		jsonData, _ := json.Marshal(getResultReq)
		resp, _ := client.Post("https://api.anti-captcha.com/getTaskResult", "application/json", bytes.NewBuffer(jsonData))
		body, _ := io.ReadAll(resp.Body)
		resp.Body.Close()

		var result GetResultResponse
		json.Unmarshal(body, &result)

		if result.Status == "ready" {
			fmt.Println("\n    ✅ TOKEN OBTIDO!")
			return result.Solution.Token, nil
		}

		if result.ErrorId != 0 {
			return "", fmt.Errorf("Erro ao obter resultado")
		}
	}

	return "", fmt.Errorf("Timeout")
}

func fazerLogin(token string) {
	fmt.Println("\n[2] FAZENDO LOGIN")
	fmt.Printf("    Email: %s\n", EMAIL)

	client := criarClienteComProxy()

	// Primeiro, acessa o site para obter cookies
	fmt.Println("    Obtendo cookies do site...")
	reqSite, _ := http.NewRequest("GET", "https://7k.bet.br", nil)
	reqSite.Header.Set("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
	respSite, err := client.Do(reqSite)
	if err != nil {
		fmt.Printf("    Erro ao acessar site: %v\n", err)
	} else {
		fmt.Printf("    Site acessado: %d, Cookies: %d\n", respSite.StatusCode, len(respSite.Cookies()))
		respSite.Body.Close()
	}

	// Faz login
	payload := map[string]string{
		"login":         EMAIL,
		"password":      SENHA,
		"captcha_token": token,
	}

	jsonData, _ := json.Marshal(payload)
	fmt.Printf("    Enviando login...\n")

	req, _ := http.NewRequest("POST", "https://7k.bet.br/api/auth/login", bytes.NewBuffer(jsonData))
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Accept", "application/json")
	req.Header.Set("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
	req.Header.Set("Origin", "https://7k.bet.br")
	req.Header.Set("Referer", "https://7k.bet.br/")

	// Adiciona cookies do site
	if respSite != nil {
		for _, cookie := range respSite.Cookies() {
			req.AddCookie(cookie)
		}
	}

	resp, err := client.Do(req)
	if err != nil {
		fmt.Printf("    ❌ Erro: %v\n", err)
		return
	}
	defer resp.Body.Close()

	body, _ := io.ReadAll(resp.Body)

	fmt.Printf("\n    Status: %d\n", resp.StatusCode)
	fmt.Printf("    Resposta: %s\n", string(body))

	if resp.StatusCode == 200 {
		fmt.Println("\n    🎉 LOGIN BEM SUCEDIDO!")
	}
}

func main() {
	fmt.Println("============================================================")
	fmt.Println("LOGIN 7k.bet.br - TURNSTILE COM PROXY")
	fmt.Println("============================================================")

	// Resolver Turnstile COM PROXY
	token, err := resolverTurnstileComProxy()
	if err != nil {
		fmt.Printf("\n❌ Erro ao resolver Turnstile: %v\n", err)

		// Se falhar com proxy, tenta sem
		fmt.Println("\nTentando sem proxy (TurnstileTaskProxyless)...")
		token, err = resolverTurnstileSemProxy()
		if err != nil {
			fmt.Printf("❌ Também falhou: %v\n", err)
			return
		}
	}

	fmt.Printf("    Token: %s...\n", token[:60])

	// Fazer login
	fazerLogin(token)

	fmt.Println("\n============================================================")
}

func resolverTurnstileSemProxy() (string, error) {
	client := &http.Client{Timeout: 120 * time.Second}

	taskReq := CreateTaskRequest{
		ClientKey: ANTICAPTCHA_KEY,
		Task: map[string]string{
			"type":       "TurnstileTaskProxyless",
			"websiteURL": "https://7k.bet.br",
			"websiteKey": TURNSTILE_SITEKEY,
		},
	}

	jsonData, _ := json.Marshal(taskReq)
	resp, _ := client.Post("https://api.anti-captcha.com/createTask", "application/json", bytes.NewBuffer(jsonData))
	body, _ := io.ReadAll(resp.Body)
	resp.Body.Close()

	var taskResp CreateTaskResponse
	json.Unmarshal(body, &taskResp)

	if taskResp.ErrorId != 0 {
		return "", fmt.Errorf("Erro: %s", taskResp.ErrorCode)
	}

	fmt.Printf("    TaskId: %d\n", taskResp.TaskId)

	getResultReq := GetResultRequest{ClientKey: ANTICAPTCHA_KEY, TaskId: taskResp.TaskId}

	for i := 0; i < 40; i++ {
		time.Sleep(3 * time.Second)

		jsonData, _ := json.Marshal(getResultReq)
		resp, _ := client.Post("https://api.anti-captcha.com/getTaskResult", "application/json", bytes.NewBuffer(jsonData))
		body, _ := io.ReadAll(resp.Body)
		resp.Body.Close()

		var result GetResultResponse
		json.Unmarshal(body, &result)

		if result.Status == "ready" {
			return result.Solution.Token, nil
		}
	}

	return "", fmt.Errorf("Timeout")
}










