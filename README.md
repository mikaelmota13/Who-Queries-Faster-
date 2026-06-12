# SGBD TPC-H Benchmark

Benchmark experimental TPC-H para PostgreSQL, MySQL, SQL Server e Oracle Free. MariaDB não entra.

> Isto não é resultado oficial auditado TPC-H. É um protocolo acadêmico reproduzível.

## Protocolo implementado

### 1. Latência sequencial

Para cada SGBD, executa um banco por vez:

```text
22 queries TPC-H × 10 iterações
```

Resultado bruto:

```text
results/sequential_raw.csv
```

Métricas:

```text
results/sequential_metrics.csv
```

Colunas principais:

```text
dbms, sf, query_id, executions, mean_latency_s, median_latency_s,
p95_latency_s, p99_latency_s, std_latency_s, min_latency_s, max_latency_s,
attempts, errors
```

### 2. Speedup / concorrência

Para cada SGBD e para cada query:

```text
threads = 1, 4, 8, 16
5 execuções por nível de threads
```

Cada cenário executa a mesma query em paralelo, uma vez por thread.

Resultados brutos:

```text
results/speedup_raw.csv
results/speedup_scenario.csv
```

Métricas:

```text
results/speedup_metrics.csv
results/speedup_latency_metrics.csv
results/dbms_speedup_summary_by_threads.csv
```

O speedup principal é calculado por vazão:

```text
throughput_speedup = throughput_threads_N / throughput_threads_1
efficiency = throughput_speedup / N
```

Também é salvo `wall_speedup`, calculado por tempo de parede:

```text
wall_speedup = mean_wall_threads_1 / mean_wall_threads_N
```

### 3. Vazão fixa por tempo

Para cada SGBD:

```text
TPC-H Q1 por 120 segundos
quantas execuções forem possíveis
```

Por padrão usa 1 thread. Para alterar:

```env
THROUGHPUT_THREADS=4
```

Resultados:

```text
results/throughput_raw.csv
results/throughput_scenario.csv
results/throughput_fixed_time_metrics.csv
```

## Limpeza de cache e planos

Após cada execução/cenário, o script tenta limpar cache e planos do SGBD:

- PostgreSQL: `CHECKPOINT`, `DISCARD PLANS`, `DISCARD ALL`.
- MySQL: `FLUSH TABLES`, `FLUSH STATUS`, `FLUSH OPTIMIZER_COSTS`.
- SQL Server: `CHECKPOINT`, `DBCC DROPCLEANBUFFERS`, `DBCC FREEPROCCACHE`, `DBCC FREESYSTEMCACHE`.
- Oracle: `ALTER SYSTEM CHECKPOINT`, `ALTER SYSTEM FLUSH BUFFER_CACHE`, `ALTER SYSTEM FLUSH SHARED_POOL`.

Limitação real: PostgreSQL e MySQL não oferecem um comando SQL portável equivalente ao `DROPCLEANBUFFERS` do SQL Server. Para cache completamente frio nesses dois, reinicie o container entre cenários. O script registra falhas de limpeza nas colunas `cache_before_ok`, `cache_after_ok` e erros associados.

## Requisitos

- Docker
- Docker Compose v2
- Git
- Linux, WSL2 ou Windows com Docker Desktop
- 16 GB RAM ou mais

## Imagens usadas

```text
postgres:16
mysql:8.4
mcr.microsoft.com/mssql/server:2022-latest
gvenzl/oracle-free:23-slim
```

## Execução recomendada

```bash
cp .env.example .env
make pull
make build
make tpch
make reset-results
make protocol-all
```

`protocol-all` executa um SGBD por vez:

```text
postgres -> mysql -> sqlserver -> oracle
```

Para executar somente um:

```bash
make tpch
make DB=postgres init-db
make DB=postgres protocol-db
make metrics
```

Outros bancos:

```bash
make DB=mysql init-db
make DB=mysql protocol-db

make DB=sqlserver init-db
make DB=sqlserver protocol-db

make DB=oracle init-db
make DB=oracle protocol-db
```

## Configurações principais

Edite `.env`:

```env
TPCH_SCALE_FACTOR=1
DBMS=postgres,mysql,sqlserver,oracle

SEQUENTIAL_ITERATIONS=10
SPEEDUP_ITERATIONS=5
SPEEDUP_THREADS=1,4,8,16
THROUGHPUT_QUERY_ID=1
THROUGHPUT_SECONDS=120
THROUGHPUT_THREADS=1
CLEAR_CACHE_BETWEEN_RUNS=true
```

## CSVs gerados

```text
results/sequential_raw.csv
results/sequential_metrics.csv
results/speedup_raw.csv
results/speedup_scenario.csv
results/speedup_metrics.csv
results/speedup_latency_metrics.csv
results/throughput_raw.csv
results/throughput_scenario.csv
results/throughput_fixed_time_metrics.csv
results/dbms_summary_metrics.csv
results/dbms_speedup_summary_by_threads.csv
```

## Gerar dados TPC-H

```bash
make tpch
```

Esse comando:

1. baixa `tpch-dbgen`;
2. compila `dbgen` e `qgen`;
3. gera os `.tbl` em `data/tpch_raw/`;
4. gera Q1–Q22 em `queries/`;
5. remove o delimitador final `|`, criando `data/tpch_clean/`.

## Levar para outra máquina

### Com internet

Copie a pasta e rode:

```bash
cp .env.example .env
make pull
make build
make tpch
make protocol-all
```

### Sem internet para baixar imagens

Na máquina com internet:

```bash
make save-images
```

Copie `docker-images/` para a outra máquina e rode:

```bash
make load-images
make build
make tpch
make protocol-all
```

Também pode copiar `data/tpch_raw`, `data/tpch_clean` e `queries` para evitar regenerar o TPC-H.

## Limpeza

Remover somente resultados:

```bash
make reset-results
```

Parar containers:

```bash
make down
```

Remover volumes, dados gerados, queries e resultados:

```bash
make clean
```
