import re
import graphviz
import sys
import os

def extraer_funciones(codigo):
    patron_funcion = re.compile(r'^def\s+(\w+)\s*\(', re.MULTILINE)
    return patron_funcion.findall(codigo)

def extraer_llamadas(codigo, funciones):
    llamadas = {funcion: [] for funcion in funciones}
    bloque_actual = None
    sangria_actual = None

    lineas = codigo.split('\n')

    for i, linea in enumerate(lineas):
        linea_limpia = linea.strip()
        if not linea_limpia or linea_limpia.startswith('#'):
            continue

        match_def = re.match(r'^(\s*)def\s+(\w+)\s*\(', linea)
        if match_def:
            sangria_actual = len(match_def.group(1))
            bloque_actual = match_def.group(2)
            continue

        if bloque_actual is not None:
            sangria_linea = len(linea) - len(linea.lstrip())
            if sangria_linea <= sangria_actual:
                bloque_actual = None
                sangria_actual = None
                continue

            for funcion in funciones:
                if re.search(r'\b' + re.escape(funcion) + r'\s*\(', linea):
                    llamadas[bloque_actual].append(funcion)

    return llamadas

def construir_grafo(llamadas):
    dot = graphviz.Digraph(comment='Mapa de llamadas de funciones')
    for origen, destinos in llamadas.items():
        dot.node(origen)
        for destino in destinos:
            dot.edge(origen, destino)
    return dot

def analizar_archivo(nombre_archivo):
    if not os.path.isfile(nombre_archivo):
        print(f"Error: no se encontró el archivo '{nombre_archivo}'")
        return

    with open(nombre_archivo, 'r', encoding='utf-8') as f:
        codigo = f.read()

    funciones = extraer_funciones(codigo)
    llamadas = extraer_llamadas(codigo, funciones)
    grafo = construir_grafo(llamadas)

    nombre_salida = os.path.splitext(nombre_archivo)[0] + '_funciones'
    grafo.render(nombre_salida, format='png', cleanup=True)
    print(f"Mapa generado como {nombre_salida}.png")

# Punto de entrada
if __name__ == '__main__':
    if len(sys.argv) != 2:
        print("Uso: python script.py archivo.py")
    else:
        analizar_archivo(sys.argv[1])
