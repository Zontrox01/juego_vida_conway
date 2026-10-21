# Juego de la Vida de Conway - Interfaz avanzada

Una interfaz gráfica completa del Juego de la Vida de Conway, hecha con `customtkinter`, con funciones ampliadas: varios tipos de célula, condiciones de contorno, estadísticas en tiempo real y **reglas de reproducción configurables desde la propia interfaz**.

> **Créditos:** este proyecto está basado en el trabajo original de [HasonCode (Harrison Adams)](https://github.com/HasonCode). Esta versión añade el panel de reglas configurables, el marcado de casillas con historia, mejoras en la visibilidad de las células muertas y la traducción completa al español.
>
![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![Customtkinter](https://img.shields.io/badge/UI-CustomTkinter-green)
![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey)
![License](https://img.shields.io/badge/license-MIT-yellow)

---

## Novedades de esta versión

- **Panel "Reglas del juego":** el usuario define gráficamente las reglas de nacimiento, supervivencia, cura y muerte, con su notación y fórmulas matemáticas (ver [más abajo](#5-reglas-de-reproducción-configurables)).
- **Células muertas visibles:** fondo negro con rejilla gris tenue, y gráficos con las muertas en gris para que no desaparezcan sobre el fondo oscuro.
- **Casillas con historia:** opción para pintar en gris las casillas muertas que han tenido vida alguna vez.
- **Reglas en el CSV:** las reglas se guardan y se cargan junto con la cuadrícula (los CSV antiguos siguen funcionando).
- **Contornos corregidos:** al limpiar la cuadrícula o cambiar su tamaño se conservan los contornos elegidos.
- **Interfaz traducida al español.**

## Características

### 1. Lienzo interactivo
- **Clic y arrastre:** haz clic para colocar células individuales o arrastra para pintar varias.
- **Representación visual:** cada tipo de célula tiene su color y su patrón (punto, aspa o cruz).
- **Rejilla:** líneas grises tenues que delimitan las casillas, también en cuadrículas grandes.

### 2. Tipos de célula
| Tipo | Color | Descripción |
|---|---|---|
| **Muerta** (🟥) | Negro | Célula muerta. Puede nacer si cumple la regla de nacimiento. |
| **Viva** (🟩) | Verde | Célula viva que sigue las reglas de Conway. |
| **Cáncer** (⬜) | Blanco | Célula agresiva que se propaga a las vecinas muertas. |
| **Cura** (🟦) | Azul | Célula especial que puede curar al cáncer. |

> En este modelo no existe una celda "vacía" distinta de la célula muerta: la casilla sin célula **es** una célula muerta. La opción de casillas con historia (ver más abajo) añade una distinción solo visual.

### 3. Condiciones de contorno
Configura cómo se comportan los bordes de la cuadrícula:
- **Normal:** las células fuera de la cuadrícula se consideran muertas.
- **Periódico:** la cuadrícula se conecta por los extremos (topología de toro).
- **Espejo:** las células del borde se reflejan.

Cada borde (izquierdo, derecho, superior e inferior) se configura de forma independiente, y un indicador de color rodea el lienzo (gris = normal, verde = periódico, naranja = espejo).

### 4. Controles de la simulación
- **Iniciar / Parar:** inicia o detiene la simulación automática.
- **Paso:** avanza una generación.
- **Velocidad:** deslizador de 10 ms a 1000 ms por iteración.
- **Limpiar:** vuelve a dejar toda la cuadrícula con células muertas.

### 5. Reglas de reproducción configurables
El panel **"Reglas del juego"** permite cambiar el comportamiento del autómata sin tocar el código. Los cambios se aplican en la siguiente generación, incluso con la simulación en marcha.

- **Notación N/S:** se muestra y se actualiza sola. `N3/S23` significa que una célula **nace** con 3 vecinas vivas y **sobrevive** con 2 o 3.
- **Selector gráfico de vecinas (0 a 8):** pulsa los números para activarlos o desactivarlos, con una mini-cuadrícula 3×3 de ejemplo.
- **Explicación matemática:** cada regla muestra su fórmula con los valores actuales.
- **Valores por defecto:** un botón por pestaña y otro para restaurarlo todo.

Hay cuatro pestañas:

| Pestaña | Qué se configura |
|---|---|
| **Nacimiento** | Nº de vecinas vivas con las que nace una célula; nacimiento de cáncer y de cura (umbral, probabilidad base y peso de referencia). |
| **Supervivencia** | Nº de vecinas vivas con las que sobrevive una célula; muerte opcional de las células vivas por contacto con cáncer (desactivada por defecto). |
| **Cáncer** | Curación del cáncer (umbral, probabilidad, resistencia, mínimo) y muerte por sobrepoblación (umbral base, mínimo, peso de referencia). |
| **Cura** | Peso por defecto, muerte por aislamiento y muerte por sobrepoblación. |

### 6. Pesos de las células
- **Peso del cáncer:** agresividad de las células de cáncer (0.0001 - 1.0).
- **Peso de la cura:** fuerza curativa de las células de cura (0.0001 - 1.0).
- **Actualización en tiempo real:** los cambios se aplican de inmediato a las células existentes.
- **Guardado y carga:** los pesos se conservan en los archivos de cuadrícula.
- **Comportamiento dinámico:** pesos más altos producen efectos más fuertes durante la simulación.

### 7. Configuración de la cuadrícula
- **Deslizador de tamaño:** de 10×10 a 60×60.
- **Escalado adaptable:** el tamaño de las celdas se ajusta solo para mantener la interfaz manejable.
- **Lienzo desplazable:** las cuadrículas grandes se muestran dentro de una zona con desplazamiento.
- **Cambio de tamaño en tiempo real:** la cuadrícula se actualiza al instante.
- **Tamaño de celda:** se muestra en píxeles como referencia.

### 8. Casillas con historia (solo visual)
Con el interruptor **"Marcar en gris las casillas que han tenido vida"** (activado por defecto), las casillas muertas que antes estuvieron ocupadas por una célula viva, de cáncer o de cura se pintan en gris. Las que nunca han tenido vida siguen negras.

- No cambia las reglas ni la simulación.
- Pintar una célula "Muerta" sobre una casilla gris borra su marca (actúa como borrador).
- La marca se reinicia al limpiar, cambiar el tamaño o cargar un archivo. No se guarda en el CSV.
- También se refleja en los GIF grabados.

### 9. Operaciones con archivos
- **Guardar cuadrícula:** exporta el estado y la configuración a un archivo CSV.
- **Cargar cuadrícula:** importa una configuración guardada.
- **Guardar gráfico:** exporta el gráfico de líneas como imagen PNG de 300 DPI (botón independiente), con metadatos y la regla de reproducción usada.
- **Grabar GIF:** captura los fotogramas de la simulación y los exporta como GIF animado.
- **Contenido del CSV:** estado de la cuadrícula, tamaño, velocidad, condiciones de contorno, pesos de las células y reglas de reproducción.
- **Animación GIF:** graba hasta 300 fotogramas, con contador de fotogramas y duración según la velocidad (mínimo 100 ms).

### 10. Estadísticas en tiempo real
- **Gráfico circular:** distribución actual de los tipos de célula.
- **Gráfico de líneas:** población de cada tipo a lo largo del tiempo.
- **Actualización en vivo:** los gráficos se actualizan solos durante la simulación.

## Instrucciones de uso

### Ejecutar la interfaz
```bash
python conway_gui.py
```

### Operaciones básicas
1. **Colocar células**
   - Selecciona un tipo de célula en el menú desplegable.
   - Haz clic en el lienzo para colocar células individuales.
   - Arrastra por el lienzo para pintar varias.

2. **Iniciar la simulación**
   - Pulsa "Iniciar" para empezar la simulación automática.
   - Usa el deslizador de velocidad para ajustar la velocidad de iteración.
   - Pulsa "Parar" para detener la simulación.
   - Usa "Paso" para avanzar manualmente.

3. **Configurar los contornos**
   - Usa los menús desplegables situados alrededor de la cuadrícula.
   - Cada borde se configura de forma independiente.
   - Los cambios se aplican de inmediato.

4. **Cambiar las reglas**
   - Abre el panel "Reglas del juego" y elige una pestaña.
   - Activa o desactiva números de vecinas, o mueve los deslizadores.
   - Pulsa "Valores por defecto" para volver a la configuración original.

5. **Guardar y cargar**
   - Pulsa "Guardar cuadrícula" para exportar el estado actual.
   - Pulsa "Cargar cuadrícula" para importar una configuración guardada.
   - Los archivos están en formato CSV para poder editarlos fácilmente.

### Funciones avanzadas

#### Comportamiento de los tipos de célula (valores por defecto)
- **Muerta → Viva:** exactamente 3 vecinas vivas (`N3`).
- **Viva → Muerta:** menos de 2 o más de 3 vecinas vivas (`S23`).
- **Propagación del cáncer:** 10 % de probabilidad de infectar a las vecinas muertas con el peso por defecto (0.01); crece con el peso.
- **Generación de cura:** 50 % de probabilidad con el peso por defecto (0.1) cuando hay 5 o más vecinas de cáncer.
- **Curación del cáncer:** si hay células de cura vecinas, el cáncer se cura con cierta probabilidad (mínimo 30 %) y pasa a ser una célula **viva**.
- **Muerte del cáncer:** muere por sobrepoblación con 7 o más vecinas de cáncer (el umbral depende del peso, con un mínimo de 5).
- **Muerte de la cura:** muere por aislamiento (6 o más vecinas muertas) o por sobrepoblación (3 o más vecinas de cura); los umbrales dependen del peso.

Todos estos valores se pueden cambiar en el panel de reglas.

#### Efectos de los modos de contorno
- **Normal:** reglas estándar de Conway con borde muerto.
- **Periódico:** crea patrones continuos que se enlazan por los bordes.
- **Espejo:** refleja los patrones en los límites, creando efectos simétricos.

#### Consejos de rendimiento
- Las cuadrículas grandes (50×50 o más) pueden ir lentas en equipos antiguos.
- Reduce la velocidad para visualizar mejor los patrones complejos.
- Usa cuadrículas pequeñas para iterar y probar más rápido.

## Formato de archivo

### Estructura del CSV
```csv
Settings
grid_size,30
speed,100
boundary_modes,normal,normal,normal,normal
cancer_weight,0.01
cure_weight,0.1
rule_birth,3
rule_survival,2,3
rule_param,viva_muere_cancer_min,0
rule_param,cancer_nace_min,1
...

Grid
Dead,Dead,Alive,Dead,...
Dead,Alive,Alive,Alive,...
...
```

- Los nombres internos de las células (`Dead`, `Alive`, `Cancer`, `Cure`) y de los contornos (`normal`, `periodic`, `mirror`) se mantienen en inglés para que los archivos guardados sigan siendo compatibles.
- Las filas `rule_*` guardan las reglas de reproducción. Los CSV anteriores, que no las incluyen, se cargan igualmente y conservan las reglas que tengas activas en ese momento.

## Dependencias
- customtkinter
- matplotlib
- Pillow (PIL)
- numpy
- tkinter (incluido en Python)

## Instalación
```bash
pip install customtkinter matplotlib pillow numpy
```

## Ejemplos

### Patrones clásicos
Prueba a dibujar estos patrones clásicos del Juego de la Vida:
- **Planeador (glider):** pequeño patrón que se desplaza.
                  ■■
                  ■■
- **Parpadeador (blinker):** oscilador sencillo.
                  ■■■
- **Bloque (block):** patrón estático.
                  ·■·
                  ··■
                  ■■■

### Patrones ampliados
Experimenta con células de cáncer y de cura:
- Coloca células de cáncer para ver su propagación agresiva.
- Añade células de cura para crear zonas de contención.
- Mezcla todos los tipos para obtener interacciones complejas.

### Reglas alternativas
Cambia el nacimiento a `N36` (activando también el 6) para obtener la variante conocida como *HighLife*, o prueba otras combinaciones en el panel de reglas.

## Solución de problemas

### Problemas comunes
1. **La interfaz no arranca:** comprueba que todas las dependencias están instaladas.
2. **Rendimiento lento:** reduce el tamaño de la cuadrícula o aumenta el intervalo de velocidad.
3. **Los gráficos no se actualizan:** comprueba que el backend de matplotlib está bien configurado.
4. **Errores al guardar o cargar:** comprueba que tienes permisos de escritura en la carpeta.

### Optimización del rendimiento
- Usa cuadrículas de menos de 50×50 para una simulación fluida en tiempo real.
- Cierra otras aplicaciones si notas retrasos.
- Ajusta el deslizador de velocidad para equilibrar la visualización y el rendimiento.

## Créditos

Proyecto original: [HasonCode (Harrison Adams)](https://github.com/HasonCode).
