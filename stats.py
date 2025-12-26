"""
Módulo de estatísticas compartilhadas para o Google Ads Clicker.
Usa threading.Lock para acesso seguro entre threads.
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
    captchas_resolvidos: int = 0
    captchas_falhos: int = 0
    dominios_clicados: List[str] = field(default_factory=list)
    ultimo_clique: str = ""
    erros: int = 0
    iniciado_em: str = ""


class StatsManager:
    """Gerenciador de estatísticas thread-safe."""
    
    def __init__(self):
        self._lock = threading.Lock()
        self._workers: Dict[int, WorkerStats] = {}
        self._global_stats = {
            "total_cliques": 0,
            "total_captchas_resolvidos": 0,
            "total_captchas_falhos": 0,
            "dominios_unicos": set(),
            "palavras_processadas": 0,
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
    
    def registrar_clique(self, worker_id: int, dominio: str):
        """Registra um clique."""
        with self._lock:
            if worker_id in self._workers:
                self._workers[worker_id].cliques_total += 1
                self._workers[worker_id].dominios_clicados.append(dominio)
                self._workers[worker_id].ultimo_clique = datetime.now().strftime("%H:%M:%S")
                self._global_stats["total_cliques"] += 1
                self._global_stats["dominios_unicos"].add(dominio)
                self._add_log(f"Worker {worker_id}: Clique em {dominio}")
    
    def registrar_captcha(self, worker_id: int, resolvido: bool):
        """Registra resultado de captcha."""
        with self._lock:
            if worker_id in self._workers:
                if resolvido:
                    self._workers[worker_id].captchas_resolvidos += 1
                    self._global_stats["total_captchas_resolvidos"] += 1
                    self._add_log(f"Worker {worker_id}: Captcha resolvido ✅")
                else:
                    self._workers[worker_id].captchas_falhos += 1
                    self._global_stats["total_captchas_falhos"] += 1
                    self._add_log(f"Worker {worker_id}: Captcha falhou ❌")
    
    def registrar_erro(self, worker_id: int, erro: str):
        """Registra um erro."""
        with self._lock:
            if worker_id in self._workers:
                self._workers[worker_id].erros += 1
                self._add_log(f"Worker {worker_id}: Erro - {erro[:50]}")
    
    def registrar_palavra_processada(self):
        """Registra uma palavra processada."""
        with self._lock:
            self._global_stats["palavras_processadas"] += 1
    
    def _add_log(self, mensagem: str):
        """Adiciona uma mensagem ao log (máximo 100 entradas)."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self._global_stats["logs"].insert(0, f"[{timestamp}] {mensagem}")
        if len(self._global_stats["logs"]) > 100:
            self._global_stats["logs"] = self._global_stats["logs"][:100]
    
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
                    "captchas_ok": w.captchas_resolvidos,
                    "captchas_fail": w.captchas_falhos,
                    "dominios": w.dominios_clicados[-5:],  # Últimos 5
                    "ultimo_clique": w.ultimo_clique,
                    "erros": w.erros,
                    "iniciado": w.iniciado_em
                })
            
            return json.dumps({
                "workers": workers_data,
                "global": {
                    "total_cliques": self._global_stats["total_cliques"],
                    "captchas_resolvidos": self._global_stats["total_captchas_resolvidos"],
                    "captchas_falhos": self._global_stats["total_captchas_falhos"],
                    "dominios_unicos": len(self._global_stats["dominios_unicos"]),
                    "palavras_processadas": self._global_stats["palavras_processadas"],
                    "inicio": self._global_stats["inicio"],
                    "workers_ativos": len([w for w in self._workers.values() if w.status not in ["finalizado", "erro"]])
                },
                "logs": self._global_stats["logs"][:20],  # Últimos 20 logs
                "dominios_lista": list(self._global_stats["dominios_unicos"])
            })


# Instância global
stats_manager = StatsManager()

