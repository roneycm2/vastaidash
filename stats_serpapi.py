"""
Módulo de estatísticas para o Google Ads Clicker com SerpApi.
Adaptado para mostrar métricas específicas da fila de anúncios.
"""

import threading
from datetime import datetime
from dataclasses import dataclass, field
from typing import Dict, List
import json


@dataclass
class WorkerStats:
    """Estatísticas de um worker individual."""
    worker_id: int
    status: str = "iniciando"
    ip_atual: str = ""
    cidade: str = ""
    estado: str = ""
    palavra_atual: str = ""
    cliques_total: int = 0
    dominios_clicados: List[str] = field(default_factory=list)
    ultimo_clique: str = ""
    tempo_total_paginas: float = 0.0
    erros: int = 0
    iniciado_em: str = ""


class StatsManagerSerpApi:
    """Gerenciador de estatísticas thread-safe para SerpApi."""
    
    def __init__(self):
        self._lock = threading.Lock()
        self._workers: Dict[int, WorkerStats] = {}
        self._global_stats = {
            "total_cliques": 0,
            "dominios_unicos": set(),
            "anuncios_encontrados": 0,
            "anuncios_restantes": 0,
            "palavras_buscadas": 0,
            "inicio": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "logs": []
        }
    
    def registrar_worker(self, worker_id: int):
        """Registra um novo worker."""
        with self._lock:
            self._workers[worker_id] = WorkerStats(
                worker_id=worker_id,
                iniciado_em=datetime.now().strftime("%H:%M:%S")
            )
            self._add_log(f"Worker {worker_id} iniciado")
    
    def atualizar_status(self, worker_id: int, status: str):
        """Atualiza o status de um worker."""
        with self._lock:
            if worker_id in self._workers:
                self._workers[worker_id].status = status
    
    def atualizar_ip(self, worker_id: int, ip: str, cidade: str = "", estado: str = ""):
        """Atualiza o IP de um worker."""
        with self._lock:
            if worker_id in self._workers:
                self._workers[worker_id].ip_atual = ip
                self._workers[worker_id].cidade = cidade
                self._workers[worker_id].estado = estado
                self._add_log(f"Worker {worker_id}: IP {ip} ({cidade}, {estado})")
    
    def atualizar_palavra(self, worker_id: int, palavra: str):
        """Atualiza a palavra atual de um worker."""
        with self._lock:
            if worker_id in self._workers:
                self._workers[worker_id].palavra_atual = palavra
    
    def registrar_clique(self, worker_id: int, dominio: str, tempo_pagina: float = 0.0):
        """Registra um clique."""
        with self._lock:
            if worker_id in self._workers:
                self._workers[worker_id].cliques_total += 1
                self._workers[worker_id].dominios_clicados.append(dominio)
                self._workers[worker_id].ultimo_clique = datetime.now().strftime("%H:%M:%S")
                self._workers[worker_id].tempo_total_paginas += tempo_pagina
                self._global_stats["total_cliques"] += 1
                self._global_stats["dominios_unicos"].add(dominio)
                self._add_log(f"Worker {worker_id}: ✅ Clique em {dominio} ({tempo_pagina:.1f}s)")
    
    def registrar_erro(self, worker_id: int, erro: str):
        """Registra um erro."""
        with self._lock:
            if worker_id in self._workers:
                self._workers[worker_id].erros += 1
                self._add_log(f"Worker {worker_id}: ❌ Erro - {erro[:50]}")
    
    def atualizar_fila(self, encontrados: int, restantes: int):
        """Atualiza estatísticas da fila de anúncios."""
        with self._lock:
            self._global_stats["anuncios_encontrados"] = encontrados
            self._global_stats["anuncios_restantes"] = restantes
    
    def registrar_busca_serpapi(self, palavra: str, anuncios_encontrados: int):
        """Registra uma busca no SerpApi."""
        with self._lock:
            self._global_stats["palavras_buscadas"] += 1
            if anuncios_encontrados > 0:
                self._add_log(f"SerpApi: '{palavra[:30]}' → {anuncios_encontrados} anúncios")
    
    def _add_log(self, mensagem: str):
        """Adiciona uma mensagem ao log (máximo 100 entradas)."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self._global_stats["logs"].insert(0, f"[{timestamp}] {mensagem}")
        if len(self._global_stats["logs"]) > 100:
            self._global_stats["logs"] = self._global_stats["logs"][:100]
    
    def add_log(self, mensagem: str):
        """Adiciona uma mensagem ao log (método público)."""
        with self._lock:
            self._add_log(mensagem)
    
    def get_stats_json(self) -> str:
        """Retorna todas as estatísticas em JSON."""
        with self._lock:
            workers_data = []
            for w in self._workers.values():
                workers_data.append({
                    "id": w.worker_id,
                    "status": w.status,
                    "ip": w.ip_atual,
                    "cidade": w.cidade,
                    "estado": w.estado,
                    "palavra": w.palavra_atual,
                    "cliques": w.cliques_total,
                    "tempo_paginas": round(w.tempo_total_paginas, 1),
                    "dominios": w.dominios_clicados[-5:],  # Últimos 5
                    "ultimo_clique": w.ultimo_clique,
                    "erros": w.erros,
                    "iniciado": w.iniciado_em
                })
            
            return json.dumps({
                "workers": workers_data,
                "global": {
                    "total_cliques": self._global_stats["total_cliques"],
                    "dominios_unicos": len(self._global_stats["dominios_unicos"]),
                    "anuncios_encontrados": self._global_stats["anuncios_encontrados"],
                    "anuncios_restantes": self._global_stats["anuncios_restantes"],
                    "palavras_buscadas": self._global_stats["palavras_buscadas"],
                    "inicio": self._global_stats["inicio"],
                    "workers_ativos": len([w for w in self._workers.values() if w.status not in ["finalizado", "erro"]])
                },
                "logs": self._global_stats["logs"][:30],
                "dominios_lista": list(self._global_stats["dominios_unicos"])
            })


# Instância global
stats_manager = StatsManagerSerpApi()

