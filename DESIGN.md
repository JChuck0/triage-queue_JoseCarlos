# DESIGN.md — Triage Queue

## 1. Elección de la estructura de datos

**Estructura elegida:** un montículo (`heapq`) que almacena tuplas `(triage_level, arrival_counter, patient)`.

### Por qué funciona

- Python compara las tuplas elemento a elemento. Primero compara el nivel de triaje, así que el nivel 1 sale antes que el 2 y el 2 antes que el 3.
- Si dos pacientes tienen el mismo nivel, desempata el `arrival_counter`, un entero que aumenta en cada `enqueue` y nunca se repite. Esto garantiza el orden FIFO estricto dentro de cada nivel.
- No uso `arrived_at` para desempatar porque dos timestamps pueden coincidir si los pacientes llegan casi a la vez. Además, como `(nivel, contador)` es único, Python nunca llega a comparar dos objetos `Patient` entre sí. Esa comparación fallaría.
- Coste: `enqueue` y `dequeue` son O(log n), y `peek` es O(1). Un nivel 1 que llega se coloca bien sin reordenar toda la cola en cada inserción.
- `list_queue` usa `sorted(...)` sobre una copia, porque el orden interno de un montículo no es el orden de atención. Cuesta O(n log n), aceptable para una operación de consulta.

### Alternativas descartadas

| Alternativa | Motivo del descarte |
|---|---|
| **Una sola `deque`** | Insertar un paciente crítico "en medio" obliga a buscar su posición y a insertar, O(n) en cada alta. |
| **Lista ordenada (`bisect.insort`)** | Insertar es O(n) y sacar del principio también, por el desplazamiento de elementos. |
| **Tres `deque` (una por nivel)** | Es una opción válida: todo es O(1) y el FIFO sale gratis. Sin embargo, el diseño queda atado a exactamente 3 niveles. Con el montículo, añadir niveles no cambia la estructura. |

Con solo 3 niveles las tres deques serían una opción igual de defendible. Elegí el montículo porque generaliza mejor y es la estructura estándar para este tipo de problema.

## 2. Un worker extrae un paciente mientras otro encola un crítico

### El problema

Si dos workers acceden a la cola a la vez sin protección, aparece una **condición de carrera**:

- Dos workers pueden ver al mismo paciente como "el siguiente" y atenderlo los dos (**doble procesamiento**).
- Dos mutaciones simultáneas pueden dejar el montículo en un estado inconsistente.
- Un patrón como `peek()` seguido de `dequeue()` es inseguro. Entre las dos llamadas, otro worker puede cambiar la cola.

### La solución

Un `threading.Lock` que hace **atómica** cada operación que lee o modifica la estructura (`enqueue`, `dequeue`, `peek`, `list_queue`, `stats`).

El orden en que muto el estado dentro de `dequeue` es:

1. **Adquirir el candado.**
2. **Comprobar si la cola está vacía** (y lanzar `EmptyQueueError` si lo está).
3. **Extraer el paciente del montículo** (`heappop`).
4. **Soltar el candado.**
5. **Devolver el paciente.**

La comprobación y la extracción ocurren dentro del mismo bloque protegido. Cuando se suelta el candado, el paciente ya no está en la estructura, y por eso ningún otro worker puede cogerlo. Esa extracción es lo que "reserva" al paciente y evita el doble procesamiento.

### Resultado en el escenario del enunciado

- Si el crítico se encola **antes** de que el otro worker haga `dequeue`, el montículo lo coloca delante y es el que sale.
- Si se encola **justo después**, el primer worker conserva el paciente que ya extrajo y el crítico será el siguiente en salir.

Ambos resultados son correctos porque cada operación se ejecuta completa y por separado.

### Notas

- `peek()` es solo informativo. Nunca debe usarse para decidir y luego actuar, porque su resultado puede quedar obsoleto al instante.
- En producción se podría usar `queue.PriorityQueue`, que ya es thread-safe. Aquí se implementa a mano para modelar y entender el problema.
- Si el sistema usara `asyncio` en un solo hilo, la carrera solo sería posible si hubiera un `await` en mitad de una operación. Como las operaciones de esta cola son síncronas y cortas, no se darían interrupciones en ese caso. Aun así, el candado protege el diseño cuando se use con hilos.