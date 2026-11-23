"""
Triage Queue - Gestor de cola de prioridad para urgencias.

Niveles de triaje: 1 = crítico, 2 = urgente, 3 = estándar.
Solo se usa la biblioteca estándar de Python.

==================== NOTAS DE DISEÑO ====================

1) Elección de la estructura de datos
   Uso un montículo (heapq) que guarda tuplas (nivel, contador, paciente).
   - Python compara las tuplas elemento a elemento: primero el nivel
     (1 antes que 2 antes que 3) y, si empatan, el contador de llegada.
   - El contador crece en cada enqueue y nunca se repite, así que el
     desempate FIFO es estricto (dos timestamps sí podrían coincidir) y
     Python nunca llega a comparar dos objetos Patient entre sí.
   - Insertar y extraer cuesta O(log n); no hay que reordenar toda la cola
     en cada inserción.
   Alternativas descartadas:
   - Una sola deque: meter un nivel 1 "en medio" obliga a buscar la posición
     y a insertar, O(n) por cada alta.
   - Lista ordenada (bisect.insort): insertar es O(n) y sacar del principio
     también, por desplazar elementos.
   - Tres deques (una por nivel): también sería válido (O(1) y FIFO gratis),
     pero el montículo escala sin cambios si mañana hay más niveles.

2) Un worker saca un paciente mientras otro encola un crítico
   Es una condición de carrera: sin protección, dos workers podrían ver al
   mismo paciente como "el siguiente" (doble procesamiento) o corromper el
   montículo con dos mutaciones simultáneas.
   Solución: un Lock que hace atómica cada operación que modifica o lee la
   estructura. Dentro del candado, en este orden:
       adquirir candado -> comprobar si está vacía -> EXTRAER el paciente
       del montículo -> soltar candado -> devolver el paciente.
   Como el paciente ya no está en la estructura cuando se suelta el candado,
   ningún otro worker puede cogerlo: ese es el "reclamo" que evita el doble
   procesamiento. Nunca se debe hacer "peek, soltar y luego dequeue", porque
   entre medias la cola puede cambiar; peek es solo informativo.
   Resultado coherente: si el crítico entra antes del dequeue, sale él; si
   entra justo después, el worker conserva el que ya extrajo y el crítico
   será el siguiente.
=========================================================
"""

import heapq
import threading
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

LEVELS = (1, 2, 3)
LEVEL_NAMES = {1: "crítico", 2: "urgente", 3: "estándar"}


class EmptyQueueError(Exception):
    """Se lanza al intentar extraer un paciente de una cola vacía."""


@dataclass(frozen=True)
class Patient:
    name: str
    triage_level: int
    arrived_at: datetime = field(default_factory=datetime.now)

    def __post_init__(self):
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("El nombre del paciente no puede estar vacío.")
        if self.triage_level not in LEVELS:
            raise ValueError(
                f"Nivel de triaje inválido: {self.triage_level!r}. Debe ser 1, 2 o 3."
            )

    def __str__(self) -> str:
        hora = self.arrived_at.strftime("%H:%M:%S")
        nivel = LEVEL_NAMES[self.triage_level]
        return f"{self.name} (nivel {self.triage_level} - {nivel}, llegó a las {hora})"


class TriageQueue:
    """Cola de prioridad: nivel 1 < 2 < 3 y, dentro de un nivel, FIFO."""

    def __init__(self):
        self._heap = []  # elementos: (nivel, contador_llegada, paciente)
        self._counter = 0
        self._lock = threading.Lock()

    def enqueue(self, patient: Patient) -> None:
        """Añade un paciente respetando nivel de triaje y orden de llegada."""
        if not isinstance(patient, Patient):
            raise TypeError("Solo se pueden encolar objetos Patient.")
        with self._lock:
            heapq.heappush(
                self._heap, (patient.triage_level, self._counter, patient)
            )
            self._counter += 1

    def dequeue(self) -> Patient:
        """Extrae y devuelve al siguiente paciente. Error si la cola está vacía."""
        with self._lock:
            if not self._heap:
                raise EmptyQueueError(
                    "No hay pacientes en espera: la cola de triaje está vacía."
                )
            _, _, patient = heapq.heappop(self._heap)
        return patient

    def peek(self) -> Optional[Patient]:
        """Devuelve al siguiente paciente sin extraerlo (None si no hay nadie)."""
        with self._lock:
            if not self._heap:
                return None
            return self._heap[0][2]

    def list_queue(self) -> list:
        """Todos los pacientes en espera, en el orden en que serán atendidos."""
        with self._lock:
            # sorted() crea una lista nueva: no altera el montículo.
            # (nivel, contador) es único, así que nunca compara Patient.
            return [patient for _, _, patient in sorted(self._heap)]

    def stats(self) -> dict:
        """Número de pacientes en espera por nivel de triaje."""
        with self._lock:
            conteo = {nivel: 0 for nivel in LEVELS}
            for nivel, _, _ in self._heap:
                conteo[nivel] += 1
            return conteo

    def __len__(self) -> int:
        with self._lock:
            return len(self._heap)


# ----------------------------- CLI -----------------------------

MENU = """
===== TRIAJE URGENCIAS =====
1. Añadir un nuevo paciente
2. Llamar al siguiente paciente
3. Ver la cola actual
4. Ver estadísticas de la cola
5. Salir
"""


def pedir_nombre() -> str:
    while True:
        nombre = input("Nombre del paciente: ").strip()
        if nombre:
            return nombre
        print("El nombre no puede estar vacío.")


def pedir_nivel() -> int:
    while True:
        texto = input("Nivel de triaje (1=crítico, 2=urgente, 3=estándar): ").strip()
        if texto in ("1", "2", "3"):
            return int(texto)
        print("Nivel inválido. Escribe 1, 2 o 3.")


def accion_anadir(cola: TriageQueue) -> None:
    paciente = Patient(pedir_nombre(), pedir_nivel())
    cola.enqueue(paciente)
    print(f"Paciente añadido: {paciente}")


def accion_llamar(cola: TriageQueue) -> None:
    try:
        paciente = cola.dequeue()
    except EmptyQueueError as error:
        print(error)
    else:
        print(f"Siguiente paciente a atender: {paciente}")


def accion_ver_cola(cola: TriageQueue) -> None:
    pacientes = cola.list_queue()
    if not pacientes:
        print("La cola está vacía.")
        return
    print(f"Siguiente: {cola.peek()}")
    print("Orden de atención:")
    for posicion, paciente in enumerate(pacientes, start=1):
        print(f"  {posicion}. {paciente}")


def accion_stats(cola: TriageQueue) -> None:
    print("Pacientes en espera por nivel:")
    for nivel, total in cola.stats().items():
        print(f"  Nivel {nivel} ({LEVEL_NAMES[nivel]}): {total}")


def main() -> None:
    cola = TriageQueue()
    acciones = {
        "1": accion_anadir,
        "2": accion_llamar,
        "3": accion_ver_cola,
        "4": accion_stats,
    }
    while True:
        print(MENU)
        try:
            opcion = input("Elige una opción: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nSaliendo...")
            break
        if opcion == "5":
            print("Hasta pronto.")
            break
        accion = acciones.get(opcion)
        if accion is None:
            print("Opción no válida. Elige un número del 1 al 5.")
            continue
        try:
            accion(cola)
        except (EOFError, KeyboardInterrupt):
            print("\nOperación cancelada.")


if __name__ == "__main__":
    main()