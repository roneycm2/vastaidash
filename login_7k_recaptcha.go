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
	ANTICAPTCHA_KEY    = "f80abc2cefe60bfec5c97f16294a1452"
	RECAPTCHA_SITEKEY  = "6Lcw3wQqAAAAAEOMFhsaVinDDCGdPdBfA68qTq2Y"
	TURNSTILE_SITEKEY  = "0x4AAAAAAAykd8yJm3kQzNJc"
	PROXY_HOST         = "pybpm-ins-hxqlzicm.pyproxy.io"
	PROXY_PORT         = "2510"
	PROXY_USER         = "liderbet1-zone-adam-region-br"
	PROXY_PASS         = "Aa10203040"
	EMAIL              = "thomasotto58@gmail.com"
	SENHA              = "Thom@s147"
)

type CreateTaskRequest struct {
	ClientKey string      `json:"clientKey"`
	Task      interface{} `json:"task"`
}

type RecaptchaV2Task struct {
	Type       string `json:"type"`
	WebsiteURL string `json:"websiteURL"`
	WebsiteKey string `json:"websiteKey"`
}

type RecaptchaV3Task struct {
	Type            string  `json:"type"`
	WebsiteURL      string  `json:"websiteURL"`
	WebsiteKey      string  `json:"websiteKey"`
	MinScore        float64 `json:"minScore"`
	PageAction      string  `json:"pageAction"`
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
		GRecaptchaResponse string `json:"gRecaptchaResponse"`
		Token              string `json:"token"`
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

func resolverRecaptchaV2() (string, error) {
	fmt.Println("\n[RECAPTCHA V2]")
	fmt.Printf("    SiteKey: %s\n", RECAPTCHA_SITEKEY)

	client := &http.Client{Timeout: 180 * time.Second}

	taskReq := CreateTaskRequest{
		ClientKey: ANTICAPTCHA_KEY,
		Task: RecaptchaV2Task{
			Type:       "RecaptchaV2TaskProxyless",
			WebsiteURL: "https://7k.bet.br",
			WebsiteKey: RECAPTCHA_SITEKEY,
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
		return "", fmt.Errorf("Erro: %s - %s", taskResp.ErrorCode, taskResp.ErrorDescription)
	}

	fmt.Printf("    TaskId: %d\n", taskResp.TaskId)
	fmt.Println("    Aguardando resolução...")

	getResultReq := GetResultRequest{ClientKey: ANTICAPTCHA_KEY, TaskId: taskResp.TaskId}

	for i := 0; i < 60; i++ {
		time.Sleep(3 * time.Second)
		fmt.Printf("    %ds...\r", (i+1)*3)

		jsonData, _ := json.Marshal(getResultReq)
		resp, _ := client.Post("https://api.anti-captcha.com/getTaskResult", "application/json", bytes.NewBuffer(jsonData))
		body, _ := io.ReadAll(resp.Body)
		resp.Body.Close()

		var result GetResultResponse
		json.Unmarshal(body, &result)

		if result.Status == "ready" {
			token := result.Solution.GRecaptchaResponse
			if token == "" {
				token = result.Solution.Token
			}
			fmt.Println("\n    ✅ TOKEN OBTIDO!")
			return token, nil
		}
	}

	return "", fmt.Errorf("Timeout")
}

func resolverRecaptchaV3() (string, error) {
	fmt.Println("\n[RECAPTCHA V3]")
	fmt.Printf("    SiteKey: %s\n", RECAPTCHA_SITEKEY)

	client := &http.Client{Timeout: 180 * time.Second}

	taskReq := CreateTaskRequest{
		ClientKey: ANTICAPTCHA_KEY,
		Task: RecaptchaV3Task{
			Type:       "RecaptchaV3TaskProxyless",
			WebsiteURL: "https://7k.bet.br",
			WebsiteKey: RECAPTCHA_SITEKEY,
			MinScore:   0.9,
			PageAction: "login",
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
		return "", fmt.Errorf("Erro: %s - %s", taskResp.ErrorCode, taskResp.ErrorDescription)
	}

	fmt.Printf("    TaskId: %d\n", taskResp.TaskId)

	getResultReq := GetResultRequest{ClientKey: ANTICAPTCHA_KEY, TaskId: taskResp.TaskId}

	for i := 0; i < 60; i++ {
		time.Sleep(3 * time.Second)
		fmt.Printf("    %ds...\r", (i+1)*3)

		jsonData, _ := json.Marshal(getResultReq)
		resp, _ := client.Post("https://api.anti-captcha.com/getTaskResult", "application/json", bytes.NewBuffer(jsonData))
		body, _ := io.ReadAll(resp.Body)
		resp.Body.Close()

		var result GetResultResponse
		json.Unmarshal(body, &result)

		if result.Status == "ready" {
			token := result.Solution.GRecaptchaResponse
			if token == "" {
				token = result.Solution.Token
			}
			fmt.Println("\n    ✅ TOKEN OBTIDO!")
			return token, nil
		}
	}

	return "", fmt.Errorf("Timeout")
}

func resolverTurnstile() (string, error) {
	fmt.Println("\n[TURNSTILE]")
	fmt.Printf("    SiteKey: %s\n", TURNSTILE_SITEKEY)

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
		fmt.Printf("    %ds...\r", (i+1)*3)

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
	}

	return "", fmt.Errorf("Timeout")
}

func fazerLogin(captchaToken, recaptchaToken string) {
	fmt.Println("\n[FAZENDO LOGIN]")

	client := criarClienteComProxy()

	// Payload com ambos os tokens
	payload := map[string]string{
		"login":         EMAIL,
		"password":      SENHA,
	}
	
	if captchaToken != "" {
		payload["captcha_token"] = captchaToken
	}
	if recaptchaToken != "" {
		payload["g-recaptcha-response"] = recaptchaToken
	}

	jsonData, _ := json.Marshal(payload)
	fmt.Printf("    Payload: %v\n", payload)

	req, _ := http.NewRequest("POST", "https://7k.bet.br/api/auth/login", bytes.NewBuffer(jsonData))
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Accept", "application/json")
	req.Header.Set("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
	req.Header.Set("Origin", "https://7k.bet.br")
	req.Header.Set("Referer", "https://7k.bet.br/")

	resp, err := client.Do(req)
	if err != nil {
		fmt.Printf("    ❌ Erro: %v\n", err)
		return
	}
	defer resp.Body.Close()

	body, _ := io.ReadAll(resp.Body)

	fmt.Printf("    Status: %d\n", resp.StatusCode)
	fmt.Printf("    Resposta: %s\n", string(body))

	if resp.StatusCode == 200 {
		fmt.Println("\n    🎉 LOGIN BEM SUCEDIDO!")
	}
}

func main() {
	fmt.Println("============================================================")
	fmt.Println("LOGIN 7k.bet.br - TESTANDO RECAPTCHA")
	fmt.Println("============================================================")

	// Tenta resolver reCAPTCHA V2
	recaptchaToken, err := resolverRecaptchaV2()
	if err != nil {
		fmt.Printf("    Erro reCAPTCHA V2: %v\n", err)
		
		// Tenta V3
		recaptchaToken, err = resolverRecaptchaV3()
		if err != nil {
			fmt.Printf("    Erro reCAPTCHA V3: %v\n", err)
		}
	}

	// Resolve Turnstile também
	turnstileToken, _ := resolverTurnstile()

	// Tenta login com diferentes combinações
	fmt.Println("\n[TESTE 1] Apenas Turnstile")
	fazerLogin(turnstileToken, "")

	fmt.Println("\n[TESTE 2] Apenas reCAPTCHA")
	fazerLogin("", recaptchaToken)

	fmt.Println("\n[TESTE 3] Ambos")
	fazerLogin(turnstileToken, recaptchaToken)

	fmt.Println("\n============================================================")
}











