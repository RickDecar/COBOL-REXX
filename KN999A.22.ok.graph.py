import traceback
import sys
from graphviz import Digraph
import os

def procesar_bloque_sql(archivo):
    for linea in archivo:
        if 'END-EXEC' in linea.upper():
            return
    return

def es_linea_ignorable(linea):
    return not linea or (len(linea) >= 7 and linea[6] == '*')

def detectar_parrafo(linea):
    if len(linea) >= 11 and linea[7:11].strip() and linea.rstrip().endswith('.'):
        posible_parrafo = linea[7:72].strip().rstrip('.')
        if posible_parrafo in ['VARYING', 'UNTIL', 'WITH']:
            return None
        return posible_parrafo
    return None

def detectar_perform(linea):
    if 'PERFORM' in linea.upper():
        partes = linea.strip().upper().split()
        try:
            idx = partes.index('PERFORM')
            destino = partes[idx + 1].rstrip('.')
            if destino in ['VARYING', 'UNTIL', 'WITH']:
                return None
            return destino
        except (IndexError, ValueError):
            return None
    return None

def filtrar_desde_parrafo_inicio(llamadas, parrafo_inicio):
    if parrafo_inicio not in llamadas:
        print(f"El párrafo '{parrafo_inicio}' no existe en el archivo.")
        return {}

    resultado = {parrafo_inicio: llamadas.get(parrafo_inicio, [])}
    for origen, destinos in list(llamadas.items()):
        pendientes = destinos.copy()
        while pendientes:
            destino = pendientes.pop()
            if destino in resultado:
                continue
            if destino in llamadas:
                resultado[origen].append(destino)
            else:
                pendientes.extend(llamadas.get(destino, []))
    return resultado

def obtener_parrafos_accesibles(llamadas, parrafo_inicio):
    accesibles = set()
    pendientes = [parrafo_inicio or '__START__']
    while pendientes:
        actual = pendientes.pop()
        if actual in accesibles:
            continue
        accesibles.add(actual)
        pendientes.extend(llamadas.get(actual, []))
    return accesibles

def analizar_cobol(ruta_archivo, parrafo_inicio=None):
    llamadas = {}
    en_procedure_division = False
    parrafo_actual = '__START__'
    bloque_sql_count = 0
    en_bloque_sql = False

    try:
        with open(ruta_archivo, 'r') as archivo:
            for linea in archivo:
                if es_linea_ignorable(linea):
                    continue

                if en_bloque_sql:
                    if 'END-EXEC' in linea.upper():
                        en_bloque_sql = False
                    continue

                if 'EXEC SQL' in linea.upper():
                    bloque_sql_count += 1
                    en_bloque_sql = True
                    continue

                if 'PROCEDURE DIVISION' in linea.upper():
                    en_procedure_division = True
                    continue

                if not en_procedure_division:
                    continue

                nuevo_parrafo = detectar_parrafo(linea)
                if nuevo_parrafo:
                    parrafo_actual = nuevo_parrafo
                    if parrafo_actual not in llamadas:
                        llamadas[parrafo_actual] = []
                    continue

                if parrafo_actual:
                    destino = detectar_perform(linea)
                    if destino:
                        llamadas.setdefault(parrafo_actual, []).append(destino)

        if parrafo_inicio:
            llamadas = filtrar_desde_parrafo_inicio(llamadas, parrafo_inicio)

        accesibles = obtener_parrafos_accesibles(llamadas, parrafo_inicio)
        llamadas = {k: v for k, v in llamadas.items() if k in accesibles}

    except Exception as e:
        print("Se ha producido un error al analizar el archivo COBOL:")
        traceback.print_exc()
        return {}, 0

    return llamadas, bloque_sql_count

def imprimir_arbol_llamadas(diccionario, nodo, nivel=0, visitados=None):
    if not nodo:
        if diccionario:
            nodo = next(iter(diccionario))
        else:
            print("Diccionario vacío. No hay llamadas que mostrar.")
            return

    if visitados is None:
        visitados = set()

    indent = '   ' * nivel
    print(f"{indent}{nodo}")
    visitados.add(nodo)

    for hijo in diccionario.get(nodo, []):
        if hijo not in visitados:
            imprimir_arbol_llamadas(diccionario, hijo, nivel + 1, visitados.copy())

def generar_grafo(diccionario, archivo_salida):
    dot = Digraph(comment='Llamadas COBOL', format='pdf', engine='dot')
    dot.attr(dpi='300')
    dot.attr('node', shape='box', style='filled', fillcolor='lightblue', fontname='Helvetica', fontsize='10')

    visitados = set()
    niveles = {}
    contador = [1]
    orden_llamadas = {}

    def asignar_niveles(nodo, nivel=0):
        if nodo in visitados:
            return
        visitados.add(nodo)
        niveles[nodo] = nivel
        for hijo in diccionario.get(nodo, []):
            orden_llamadas[(nodo, hijo)] = contador[0]
            contador[0] += 1
            asignar_niveles(hijo, nivel + 1)

    nodo_raiz = '__START__'
    if nodo_raiz not in diccionario:
        nodo_raiz = next(iter(diccionario))
    asignar_niveles(nodo_raiz)

    niveles_invertido = {}
    for nodo, nivel in niveles.items():
        niveles_invertido.setdefault(nivel, []).append(nodo)

    for nivel in sorted(niveles_invertido):
        with dot.subgraph() as s:
            s.attr(rank='same')
            for nodo in niveles_invertido[nivel]:
                s.node(nodo)

    for (origen, destino), numero in orden_llamadas.items():
        dot.edge(origen, destino, color='blue', style='solid', arrowsize='0.5', label=str(numero))

    dot.render(archivo_salida, cleanup=True)
    print(f"Grafo generado: {archivo_salida}.pdf")

def guardar_diccionario(diccionario, nombre_archivo_salida):
    nombre_base = nombre_archivo_salida
    archivo_salida = f"{nombre_base}.txt"

    with open(archivo_salida, 'w') as f:
        for clave, llamadas in diccionario.items():
            f.write(f"{clave}:\n")
            for llamada in llamadas:
                f.write(f"  - {llamada}\n")
            f.write("\n")

    print(f"Diccionario de llamadas guardado en: {archivo_salida}")

# MAIN
if len(sys.argv) > 1:
    ruta_del_programa_cobol = sys.argv[1]
    parrafo_inicio = sys.argv[2] if len(sys.argv) > 2 else None
else:
    ruta_del_programa_cobol = input("Por favor, ingresa la ruta del programa COBOL: ")
    parrafo_inicio = input("Si deseas comenzar desde un párrafo específico, ingrésalo (de lo contrario, deja en blanco): ")

diccionario_llamadas, bloques_exec_sql = analizar_cobol(ruta_del_programa_cobol, parrafo_inicio)

print(diccionario_llamadas)
print(f"Total de bloques EXEC SQL encontrados: {bloques_exec_sql}")
print("Relaciones de llamadas:")

imprimir_arbol_llamadas(diccionario_llamadas, '')

nombre_archivo_salida = os.path.splitext(ruta_del_programa_cobol)[0]
generar_grafo(diccionario_llamadas, nombre_archivo_salida)
guardar_diccionario(diccionario_llamadas, nombre_archivo_salida)
