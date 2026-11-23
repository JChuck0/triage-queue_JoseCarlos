# 🏥 Triage Queue — Gestor de Cola de Prioridad

Gestor de cola de triaje para una unidad de urgencias, escrito en Python y ejecutable desde terminal. Modela una **cola de prioridad con desempate por orden de llegada** y está pensado para integrarse más adelante en una aplicación mayor.

## 📋 Contexto

Un hospital público quiere sustituir la pizarra manual donde una enfermera apunta a los pacientes. Ese sistema genera problemas cuando llega un caso crítico y hay que saltarse la cola, o cuando dos personas actualizan la pizarra a la vez y se borra una entrada. Este proyecto resuelve ese problema con un gestor de colas fiable.

## ✨ Características

- Tres niveles de triaje: **1 = crítico**, **2 = urgente**, **3 = estándar**.
- El nivel 1 siempre se atiende antes que el 2, y el 2 antes que el 3.
- Dentro del mismo nivel, los pacientes se atienden en **orden estricto de llegada (FIFO)**.
- Menú interactivo por terminal, robusto ante entradas inválidas.
- Solo biblioteca estándar de Python. **Sin dependencias externas.**
- Operaciones protegidas con un candado para uso seguro con varios workers.

## 🚀 Requisitos y ejecución

**Requisitos:** Python 3.8 o superior.

```bash
python triage_queue.py
```

### Menú

```
===== TRIAJE URGENCIAS =====
1. Añadir un nuevo paciente
2. Llamar al siguiente paciente
3. Ver la cola actual
4. Ver estadísticas de la cola
5. Salir
```

## 🧩 Arquitectura

| Componente | Responsabilidad |
|---|---|
| `Patient` | Dataclass inmutable con `name`, `triage_level` (1–3) y `arrived_at`. Valida sus datos al crearse. |
| `TriageQueue` | Toda la lógica de la cola de prioridad. |
| `EmptyQueueError` | Excepción propia para extraer de una cola vacía. |
| Funciones `accion_*` y `main()` | Interfaz de terminal. No contienen lógica de cola. |

### API de `TriageQueue`

| Método | Descripción |
|---|---|
| `enqueue(patient)` | Añade un paciente respetando nivel de triaje y orden de llegada. |
| `dequeue()` | Extrae y devuelve al siguiente paciente. Lanza `EmptyQueueError` si la cola está vacía. |
| `peek()` | Devuelve al siguiente paciente sin extraerlo (`None` si no hay nadie). |
| `list_queue()` | Lista de todos los pacientes en espera, en orden de atención. |
| `stats()` | Diccionario con el número de pacientes en espera por nivel de triaje. |

### Ejemplo de uso

```python
from triage_queue import Patient, TriageQueue

cola = TriageQueue()
cola.enqueue(Patient("Ana", 3))
cola.enqueue(Patient("Luis", 2))
cola.enqueue(Patient("Marta", 1))   # crítico: pasa delante de los demás

print(cola.peek())         # Marta
print(cola.stats())        # {1: 1, 2: 1, 3: 1}
print(cola.dequeue())      # Marta
print(cola.dequeue())      # Luis
```

## 🧠 Decisiones de diseño

**Estructura de datos:** un montículo (`heapq`) con tuplas `(nivel, contador, paciente)`. El contador de llegada garantiza el FIFO dentro de cada nivel, ya que dos timestamps podrían coincidir. Insertar y extraer cuesta O(log n) sin reordenar la cola completa.

**Concurrencia:** cada operación se ejecuta dentro de un `threading.Lock`. En `dequeue`, el paciente se extrae de la estructura *antes* de soltar el candado, de modo que dos workers nunca pueden atender al mismo paciente.

El razonamiento completo, con las alternativas descartadas, está en [`DESIGN.md`](DESIGN.md).

## ✅ Casos borde cubiertos

- Un paciente crítico que llega con pacientes de nivel 2 y 3 esperando se coloca delante de ellos.
- Dos pacientes con el mismo nivel se atienden en orden de llegada.
- `dequeue()` sobre una cola vacía lanza un error descriptivo que la interfaz gestiona sin romperse.
- `peek()` sobre una cola vacía devuelve `None`.
- Nombres vacíos, niveles fuera de 1–3, opciones de menú inválidas y `Ctrl+C`/fin de entrada se gestionan sin romper el programa.

## 📁 Estructura del proyecto

```
.
├── triage_queue.py   # Código: modelo, cola y CLI
├── DESIGN.md         # Notas de diseño y concurrencia
└── README.md         # Este archivo
```

## 🔭 Posibles mejoras

- Tests automatizados con `unittest` o `pytest`.
- Persistencia de la cola entre ejecuciones.
- Soporte de más niveles de prioridad o reclasificación de pacientes.
- Interfaz gráfica o API web sobre la misma clase `TriageQueue`.