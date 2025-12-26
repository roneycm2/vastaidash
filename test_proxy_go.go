package main

import (
	"crypto/tls"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"time"
)

func testarProxy(nome, proxyURL string) {
	fmt.Printf("\n[%s]\n", nome)
	fmt.Printf("URL: %s\n", proxyURL)
	
	parsedProxy, err := url.Parse(proxyURL)
	if err != nil {
		fmt.Printf("Erro ao parsear: %v\n", err)
		return
	}
	
	transport := &http.Transport{
		Proxy:           http.ProxyURL(parsedProxy),
		TLSClientConfig: &tls.Config{InsecureSkipVerify: true},
	}
	
	client := &http.Client{
		Transport: transport,
		Timeout:   15 * time.Second,
	}
	
	resp, err := client.Get("https://api.ipify.org?format=json")
	if err != nil {
		fmt.Printf("Erro: %v\n", err)
		return
	}
	defer resp.Body.Close()
	
	body, _ := io.ReadAll(resp.Body)
	var result map[string]string
	json.Unmarshal(body, &result)
	
	fmt.Printf("IP: %s\n", result["ip"])
}

func main() {
	fmt.Println("============================================================")
	fmt.Println("TESTE DE PROXIES - GO")
	fmt.Println("============================================================")
	
	// Proxy 1
	testarProxy("PROXY 1 - pybpm-ins", 
		"http://liderbet1-zone-adam-region-br:Aa10203040@pybpm-ins-hxqlzicm.pyproxy.io:2510")
	
	// Proxy 2
	testarProxy("PROXY 2 - shg.na", 
		"http://liderbet1-zone-resi-region-br:Aa10203040@fb29d01db8530b99.shg.na.pyproxy.io:16666")
	
	// Proxy 3 - com session
	testarProxy("PROXY 3 - shg.na (session)", 
		"http://liderbet1-zone-resi-region-br-session-test123-sessTime-1:Aa10203040@fb29d01db8530b99.shg.na.pyproxy.io:16666")
	
	fmt.Println("\n============================================================")
}











