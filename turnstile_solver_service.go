package main

import (
	"bytes"
	"crypto/tls"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"net/url"
	"time"
)

/*
Serviço de Resolução de Cloudflare Turnstile em Go
Usa Anti-Captcha API para resolver o captcha.

Endpoints:
  POST /solve       - Resolve um Turnstile e retorna o token
  POST /login       - Resolve Turnstile e faz login no 7k.bet.br
  GET  /health      - Verifica se o serviço está funcionando

Uso:
  go run turnstile_solver_service.go

Requisição:
  POST http://localhost:5099/solve
  {
    "sitekey": "0x4AAAAAAAykd8yJm3kQzNJc",
    "url": "https://7k.bet.br"
  }
*/

// Configuração
const (
	ANTICAPTCHA_KEY = "f80abc2cefe60bfec5c97f16294a1452"
	PROXY_HOST      = "pybpm-ins-hxqlzicm.pyproxy.io"
	PROXY_PORT      = "2510"
	PROXY_USER      = "liderbet1-zone-adam-region-br"
	PROXY_PASS      = "Aa10203040"
)

// Estruturas Anti-Captcha
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

// Estruturas da API
type SolveRequest struct {
	SiteKey string `json:"sitekey"`
	URL     string `json:"url"`
	Timeout int    `json:"timeout"`
}

type SolveResponse struct {
	Success   bool    `json:"success"`
	Token     string  `json:"token,omitempty"`
	Error     string  `json:"error,omitempty"`
	TimeTaken float64 `json:"time_taken"`
}

type LoginRequest struct {
	Email    string `json:"email"`
	Password string `json:"password"`
}

type LoginResponse struct {
	Success      bool        `json:"success"`
	StatusCode   int         `json:"status_code"`
	Response     interface{} `json:"response"`
	Cookies      []string    `json:"cookies,omitempty"`
	TurnstileTime float64    `json:"turnstile_time"`
	Error        string      `json:"error,omitempty"`
}

// Cliente HTTP com proxy
func criarClienteComProxy() *http.Client {
	proxyURL, _ := url.Parse(fmt.Sprintf("http://%s:%s@%s:%s", PROXY_USER, PROXY_PASS, PROXY_HOST, PROXY_PORT))
	transport := &http.Transport{
		Proxy:           http.ProxyURL(proxyURL),
		TLSClientConfig: &tls.Config{InsecureSkipVerify: true},
	}
	return &http.Client{Transport: transport, Timeout: 60 * time.Second}
}

// Cliente HTTP sem proxy (para Anti-Captcha)
func criarClienteSemProxy() *http.Client {
	return &http.Client{Timeout: 120 * time.Second}
}

// Resolve Turnstile via Anti-Captcha
func resolverTurnstile(sitekey, pageURL string, timeout int) SolveResponse {
	start := time.Now()
	result := SolveResponse{Success: false}

	client := criarClienteSemProxy()

	// 1. Criar tarefa
	log.Printf("[Solver] Criando tarefa para %s...", pageURL)

	taskReq := CreateTaskRequest{
		ClientKey: ANTICAPTCHA_KEY,
		Task: TurnstileTask{
			Type:       "TurnstileTaskProxyless",
			WebsiteURL: pageURL,
			WebsiteKey: sitekey,
		},
	}

	jsonData, _ := json.Marshal(taskReq)
	resp, err := client.Post("https://api.anti-captcha.com/createTask", "application/json", bytes.NewBuffer(jsonData))
	if err != nil {
		result.Error = fmt.Sprintf("Erro ao criar tarefa: %v", err)
		return result
	}
	defer resp.Body.Close()

	body, _ := io.ReadAll(resp.Body)
	var taskResp CreateTaskResponse
	json.Unmarshal(body, &taskResp)

	if taskResp.ErrorId != 0 {
		result.Error = fmt.Sprintf("Anti-Captcha erro: %s - %s", taskResp.ErrorCode, taskResp.ErrorDescription)
		return result
	}

	log.Printf("[Solver] TaskId: %d", taskResp.TaskId)

	// 2. Aguardar resultado
	getResultReq := GetResultRequest{
		ClientKey: ANTICAPTCHA_KEY,
		TaskId:    taskResp.TaskId,
	}

	maxAttempts := timeout / 3
	if maxAttempts < 20 {
		maxAttempts = 20
	}

	for i := 0; i < maxAttempts; i++ {
		time.Sleep(3 * time.Second)

		jsonData, _ := json.Marshal(getResultReq)
		resp, err := client.Post("https://api.anti-captcha.com/getTaskResult", "application/json", bytes.NewBuffer(jsonData))
		if err != nil {
			continue
		}

		body, _ := io.ReadAll(resp.Body)
		resp.Body.Close()

		var getResult GetResultResponse
		json.Unmarshal(body, &getResult)

		if getResult.Status == "ready" {
			result.Success = true
			result.Token = getResult.Solution.Token
			result.TimeTaken = time.Since(start).Seconds()
			log.Printf("[Solver] Token obtido em %.2fs", result.TimeTaken)
			return result
		}

		if i%5 == 0 {
			log.Printf("[Solver] Aguardando... %ds", (i+1)*3)
		}
	}

	result.Error = "Timeout ao resolver Turnstile"
	result.TimeTaken = time.Since(start).Seconds()
	return result
}

// Faz login no 7k.bet.br
func fazerLogin7k(email, password, captchaToken string) LoginResponse {
	result := LoginResponse{Success: false}

	client := criarClienteComProxy()

	// 1. Primeiro acessa o site para pegar cookies do Cloudflare
	log.Println("[Login] Acessando site para obter cookies...")
	
	reqSite, _ := http.NewRequest("GET", "https://7k.bet.br", nil)
	reqSite.Header.Set("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
	reqSite.Header.Set("Accept", "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8")
	reqSite.Header.Set("Accept-Language", "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7")
	
	respSite, err := client.Do(reqSite)
	if err != nil {
		log.Printf("[Login] Erro ao acessar site: %v", err)
	} else {
		respSite.Body.Close()
		log.Printf("[Login] Site acessado, cookies: %d", len(respSite.Cookies()))
	}

	// 2. Faz a requisição de login
	payload := map[string]string{
		"login":         email,
		"password":      password,
		"captcha_token": captchaToken,
	}

	jsonData, _ := json.Marshal(payload)
	log.Printf("[Login] Enviando login com token: %s...", captchaToken[:50])

	req, _ := http.NewRequest("POST", "https://7k.bet.br/api/auth/login", bytes.NewBuffer(jsonData))
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Accept", "application/json")
	req.Header.Set("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
	req.Header.Set("Origin", "https://7k.bet.br")
	req.Header.Set("Referer", "https://7k.bet.br/")
	req.Header.Set("Accept-Language", "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7")
	req.Header.Set("sec-ch-ua", `"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"`)
	req.Header.Set("sec-ch-ua-mobile", "?0")
	req.Header.Set("sec-ch-ua-platform", `"Windows"`)
	req.Header.Set("sec-fetch-dest", "empty")
	req.Header.Set("sec-fetch-mode", "cors")
	req.Header.Set("sec-fetch-site", "same-origin")

	// Adiciona cookies do site se existirem
	if respSite != nil {
		for _, cookie := range respSite.Cookies() {
			req.AddCookie(cookie)
		}
	}

	resp, err := client.Do(req)
	if err != nil {
		result.Error = fmt.Sprintf("Erro na requisição: %v", err)
		log.Printf("[Login] Erro: %v", err)
		return result
	}
	defer resp.Body.Close()

	body, _ := io.ReadAll(resp.Body)
	log.Printf("[Login] Status: %d, Body: %s", resp.StatusCode, string(body)[:min(200, len(body))])

	result.StatusCode = resp.StatusCode
	result.Success = resp.StatusCode == 200

	var jsonResp interface{}
	if err := json.Unmarshal(body, &jsonResp); err == nil {
		result.Response = jsonResp
	} else {
		result.Response = string(body)
	}

	// Captura cookies
	for _, cookie := range resp.Cookies() {
		result.Cookies = append(result.Cookies, fmt.Sprintf("%s=%s", cookie.Name, cookie.Value))
	}

	return result
}

// Handlers HTTP
func healthHandler(w http.ResponseWriter, r *http.Request) {
	json.NewEncoder(w).Encode(map[string]string{
		"status":  "ok",
		"service": "Turnstile Solver",
	})
}

func solveHandler(w http.ResponseWriter, r *http.Request) {
	if r.Method != "POST" {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	var req SolveRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		json.NewEncoder(w).Encode(SolveResponse{
			Success: false,
			Error:   "JSON inválido",
		})
		return
	}

	if req.SiteKey == "" || req.URL == "" {
		json.NewEncoder(w).Encode(SolveResponse{
			Success: false,
			Error:   "sitekey e url são obrigatórios",
		})
		return
	}

	timeout := req.Timeout
	if timeout == 0 {
		timeout = 120
	}

	log.Printf("[API] Resolvendo Turnstile para %s", req.URL)

	result := resolverTurnstile(req.SiteKey, req.URL, timeout)

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(result)
}

func loginHandler(w http.ResponseWriter, r *http.Request) {
	if r.Method != "POST" {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	var req LoginRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		json.NewEncoder(w).Encode(LoginResponse{
			Success: false,
			Error:   "JSON inválido",
		})
		return
	}

	if req.Email == "" || req.Password == "" {
		json.NewEncoder(w).Encode(LoginResponse{
			Success: false,
			Error:   "email e password são obrigatórios",
		})
		return
	}

	log.Printf("[API] Login para %s", req.Email)

	// 1. Resolver Turnstile
	solveResult := resolverTurnstile("0x4AAAAAAAykd8yJm3kQzNJc", "https://7k.bet.br", 120)

	if !solveResult.Success {
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(LoginResponse{
			Success:       false,
			Error:         "Falha ao resolver Turnstile: " + solveResult.Error,
			TurnstileTime: solveResult.TimeTaken,
		})
		return
	}

	// 2. Fazer login
	loginResult := fazerLogin7k(req.Email, req.Password, solveResult.Token)
	loginResult.TurnstileTime = solveResult.TimeTaken

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(loginResult)
}

func main() {
	fmt.Println("============================================================")
	fmt.Println("TURNSTILE SOLVER SERVICE (Go)")
	fmt.Println("============================================================")
	fmt.Println("Endpoints:")
	fmt.Println("  GET  /health  - Status do serviço")
	fmt.Println("  POST /solve   - Resolve um Turnstile")
	fmt.Println("  POST /login   - Resolve e faz login no 7k")
	fmt.Println("============================================================")
	fmt.Println("Iniciando em http://localhost:5099")
	fmt.Println("============================================================")

	http.HandleFunc("/health", healthHandler)
	http.HandleFunc("/solve", solveHandler)
	http.HandleFunc("/login", loginHandler)

	log.Fatal(http.ListenAndServe(":5099", nil))
}

