package main

import (
	"bytes"
	"crypto/tls"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"sync"
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

type TurnstileTask struct {
	Type       string `json:"type"`
	WebsiteURL string `json:"websiteURL"`
	WebsiteKey string `json:"websiteKey"`
}

type CreateTaskResponse struct {
	ErrorId int    `json:"errorId"`
	TaskId  int    `json:"taskId"`
}

type GetResultRequest struct {
	ClientKey string `json:"clientKey"`
	TaskId    int    `json:"taskId"`
}

type GetResultResponse struct {
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

func resolverTurnstile() string {
	client := &http.Client{Timeout: 120 * time.Second}

	taskReq := CreateTaskRequest{
		ClientKey: ANTICAPTCHA_KEY,
		Task: TurnstileTask{
			Type:       "TurnstileTaskProxyless",
			WebsiteURL: "https://7k.bet.br",
			WebsiteKey: TURNSTILE_SITEKEY,
		},
	}

	jsonData, _ := json.Marshal(taskReq)
	resp, _ := client.Post("https://api.anti-captcha.com/createTask", "application/json", bytes.NewBuffer(jsonData))
	body, _ := io.ReadAll(resp.Body)
	resp.Body.Close()

	var taskResp CreateTaskResponse
	json.Unmarshal(body, &taskResp)
	fmt.Printf("TaskId: %d\n", taskResp.TaskId)

	getResultReq := GetResultRequest{ClientKey: ANTICAPTCHA_KEY, TaskId: taskResp.TaskId}

	for i := 0; i < 40; i++ {
		time.Sleep(3 * time.Second)
		fmt.Printf("Aguardando... %ds\r", (i+1)*3)

		jsonData, _ := json.Marshal(getResultReq)
		resp, _ := client.Post("https://api.anti-captcha.com/getTaskResult", "application/json", bytes.NewBuffer(jsonData))
		body, _ := io.ReadAll(resp.Body)
		resp.Body.Close()

		var result GetResultResponse
		json.Unmarshal(body, &result)

		if result.Status == "ready" {
			fmt.Println("\nToken obtido!")
			return result.Solution.Token
		}
	}
	return ""
}

func fazerLogin(token, campo string) (int, string) {
	client := criarClienteComProxy()

	payload := map[string]string{
		"login":    EMAIL,
		"password": SENHA,
		campo:      token,
	}

	jsonData, _ := json.Marshal(payload)

	req, _ := http.NewRequest("POST", "https://7k.bet.br/api/auth/login", bytes.NewBuffer(jsonData))
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Accept", "application/json")
	req.Header.Set("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
	req.Header.Set("Origin", "https://7k.bet.br")
	req.Header.Set("Referer", "https://7k.bet.br/")

	resp, err := client.Do(req)
	if err != nil {
		return 0, err.Error()
	}
	defer resp.Body.Close()

	body, _ := io.ReadAll(resp.Body)
	return resp.StatusCode, string(body)
}

func main() {
	fmt.Println("============================================================")
	fmt.Println("LOGIN 7k.bet.br - RAPIDO")
	fmt.Println("============================================================")

	// Resolver Turnstile
	fmt.Println("\n[1] Resolvendo Turnstile...")
	token := resolverTurnstile()
	if token == "" {
		fmt.Println("Erro ao resolver")
		return
	}
	fmt.Printf("Token: %s...\n", token[:60])

	// Testar diferentes campos IMEDIATAMENTE
	fmt.Println("\n[2] Testando login com diferentes campos...")

	campos := []string{
		"captcha_token",
		"cf-turnstile-response",
		"turnstile_token",
		"captcha",
		"token",
		"turnstile",
		"cf_turnstile_response",
	}

	var wg sync.WaitGroup
	resultados := make(chan string, len(campos))

	for _, campo := range campos {
		wg.Add(1)
		go func(c string) {
			defer wg.Done()
			status, resp := fazerLogin(token, c)
			resultado := fmt.Sprintf("Campo '%s': Status %d - %s", c, status, resp[:min(100, len(resp))])
			resultados <- resultado
			
			if status == 200 {
				fmt.Printf("\n🎉 SUCESSO com campo '%s'!\n", c)
				fmt.Println(resp)
			}
		}(campo)
	}

	// Aguarda todos terminarem
	go func() {
		wg.Wait()
		close(resultados)
	}()

	// Imprime resultados
	fmt.Println("\nResultados:")
	for r := range resultados {
		fmt.Println(r)
	}

	fmt.Println("\n============================================================")
}

func min(a, b int) int {
	if a < b {
		return a
	}
	return b
}











