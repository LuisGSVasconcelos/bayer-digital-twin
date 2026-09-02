# Comparação: Modelo Implementado × Modelo do Artigo

**Artigo:** *Modeling of Washing Circuits in Mining – A Networked System Approach* (Tri Tran & Q. P. Ha, 2015) — `Modeling_of_Washing_Circuits_in_Mining_A.pdf`

**Implementação:** Digital Twin do Processo Bayer (`projeto_bayer`) — módulos Python + LangGraph + controle PI/Fuzzy + HITL + Streamlit.

---

## 1. Objeto modelado

| | **Artigo** | **Implementado** |
|---|---|---|
| Processo | Circuito de lavagem **contracorrente** em refinaria de alumina (recuperação de soda cáustica de resíduos), e predesilicação | Estágio de **clarificação/decantação** do Processo Bayer (decantadores PA/PB + tanques S1/S2) |
| Foco físico | Nível de sólido de underflow (`hu`), nível de licor de overflow (`ho`), densidade do sólido (`ρu`) por estágio | Nível dos decantadores (%), concentração cáustica **TC**, perda de soda, teor de sílica, chuva, vazões |

## 2. Forma do modelo

| | **Artigo** | **Implementado** |
|---|---|---|
| Formato | **Espaço de estados LTI** contínuo: `ẋ = Ax + Bu + Ev`, `w=Fx`, `v=Hw`, `y=Cx` (modelo orientado a interações/"two-port") | **Simulador por ciclos discretos**, orientado a objetos, + agente (LangGraph) |
| Equações | **EDOs não-lineares de 1ª princípio**, **linearizadas** em torno do ponto nominal (`ρu1o,…,ρu3o`) → matrizes A/B/E/C/F/H dadas | **Balanços de massa discretizados** por ciclo (volume, caustica, sólidos), sem matrizes explícitas |
| Interações | Matriz de acoplamento global `H` (elementos 0/1) conectando os subsistemas | Topologia S1→S2→divisão→PA/PB com fluxos de material explícitos entre tanques |
| Granularidade | 3 estágios (T-1,T-2,T-3) × 3 estados = 9 estados; depois hierarquia **Units/Subsystems** (em paralelo) | 4 tanques (S1,S2,PA,PB), cada um com nível; + estado de TC globais |

## 3. Estrutura e acoplamento (a parte MAIS semelhante)

O ponto central do artigo é modelar o processo como **sistema interconectado** com:
- **Conexões seriais** (o underflow/de resíduo é alimentação do próximo estágio; o overflow/ liquor vai ao estágio anterior — contracorrente).
- **Conexões paralelas / streams de reserva** (Seção IV): quando há **divisão de fluxo** em streams paralelos com **ratios de divisão variantes no tempo e desconhecidos**, modelados via unidades `Gj` com matrizes `Ψv`/`Ψw` de split e interconexão `Hππ`/`Hσ`.

**A implementação captura essa mesma física de forma simplificada:**
- Divisor S2 → **PA/PB** (decantadores paralelos) com `fator_divisao` **variante no tempo** (random-walk 0,25–0,58) → equivalente ao "split ratio dinâmico" da Seção IV.
- Fluxos seriais S1→S2→decantadores e retorno de drenagem/overflow (o artigo: underflow/overflow dos tanques).
- Não há a hierarquia formal de **Units/Subsystems** com matrizes `Ψ`/`Hππ` — a implementação resolve o split empiricamente, não como matriz de interconexão.

## 4. Controle

| | **Artigo** | **Implementado** |
|---|---|---|
| Paradigma | **MPC descentralizado/distribuído** sobre o modelo LTI (controle multivarizável); controle em cascata (nível→vazão de bomba) | **PI bidirecional** (drenagem + makeup) com banda/integral/anti-windup; **Fuzzy adaptativo** selecionável |
| Laranja | Foca no **modelo** para projeto de MPC (não há resultados de controle neste paper) | Entrega **controle funcional** + **HITL** (aprovação humana) + agente LLM + **override manual** da válvula |
| Setpoint | Níveis de resíduo/licor por estágio | Nível dos decantadores em **65%** |

## 5. Distúrbios e validação

| | **Artigo** | **Implementado** |
|---|---|---|
| Distúrbios | Apenas os **inputs de interação `v`** (estrutural, via `H`); sem clima/química | Rico: **chuva (API/Manual em mm/s)**, desgaste de bomba, stiction de válvula, desbalanceamento PA/PB, diluição de TC, sílica (perda de NaOH), picos de sensor |
| Validação | **Nenhuma** simulação/validação numérica neste paper ("utilizados em trabalhos anteriores"): matrizes dadas de projeto real | **Validado**: 25 testes pytest, benchmark honesto (RMSE 8,14→7,81, **+4,1%**), dashboard operacional; física verificada (chuva acumula, TC estabiliza ~187, nível segura em 65 com/sem chuva) |
| Unidades | m, m³/h, kg/m³ | L, %, L/s, mm/s |

## 6. Principais diferenças (resumo honesto)

1. **Formalismo:** o artigo é um **modelo LTI contínuo em espaço de estados** (equações linearizadas + matrizes) para projeto de MPC; a implementação é um **simulador discreto por balanços físicos** + agente, sem matrizes A/B/C.
2. **Química:** o artigo modela níveis de sólido/licor/densidade; a implementação modela **caustica (TC)**, **perda de soda por sílica** e **diluição** — preenchendo a "recuperação de soda" que é o propósito declarado do artigo.
3. **Distúrbios/clima:** a implementação inclui **chuva e desgaste/stiction** — fora do escopo estrutural do artigo.
4. **Controle:** artigo → **MPC**; implementação → **PI/Fuzzy + HITL + agente LLM** (paradigma agêntico/pedagógico, não MPC).
5. **Split dinâmico (Seção IV):** o artigo formaliza splits **variantes no tempo/desconhecidos** com hierarquia Units/Subsystems + `Ψ`; a implementação resolve o split com um **random-walk simples** (`fator_divisao`), mesma ideia, formalismo mais simples.
6. **Validação:** a implementação **é testada e verificada**; o artigo **não apresenta resultados numéricos** neste paper (é um paper de modelagem).

## 7. O que aproveitar / convergências para próximos passos
- A topologia **série + divisão paralela** da implementação corresponde à **Seção IV (parallelized streams)** do artigo — a escolha de PA/PB não é arbitrária, e o **`fator_divisao` variante no tempo** segue o que o artigo aponta como o desafio dos "splitting ratios dinâmicos".
- A **recuperação de soda cáustica** (balanço de caustica da implementação) é o **objetivo** do circuito de lavagem no artigo — convergência conceitual.
- Possível extensão: derivar a **representação em espaço de estados** (matrizes A/B de um tanque linearizado) para viabilizar um comparativo **MPC × PI/Fuzzy** — usando os parâmetros de projeto do artigo como referência de magnitude (ex.: ganhos `a11…a34`, `b11…b32`).