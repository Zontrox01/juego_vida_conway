# 🎬 Guía de grabación de GIF

## Resumen
La interfaz del Juego de la Vida permite grabar una simulación y exportarla como un GIF animado.

## 🎯 Cómo se usa

### **1. Empezar a grabar**
1. Prepara el patrón inicial en la cuadrícula.
2. Pulsa el botón **"Grabar GIF"**.
3. El botón se pone rojo y pasa a decir **"Detener grabación"**.
4. Aparece un aviso de confirmación con los detalles de la grabación.

### **2. Capturar la simulación**
- **Paso a paso:** pulsa **"Paso"** para capturar cada fotograma manualmente.
- **Simulación continua:** pulsa **"Iniciar"** para ejecutar la simulación y capturar los fotogramas automáticamente (se detiene con **"Parar"**).
- **Límite de fotogramas:** la grabación admite como máximo **300 fotogramas** para evitar problemas de memoria; al alcanzarlo dejan de capturarse más.

### **3. Terminar la grabación**
1. Pulsa el botón rojo **"Detener grabación"**.
2. Responde "Sí" cuando se te pregunte si quieres guardar el GIF.
3. Elige el nombre y la carpeta en el cuadro de diálogo.
4. El GIF se guarda con esa configuración.

## ✨ Características

### **🎨 Calidad visual**
- **Rejilla tenue:** el GIF muestra el fondo negro con la misma rejilla gris tenue que la pantalla, para distinguir las casillas.
- **Casillas con historia:** si está activada la opción *"Marcar en gris las casillas que han tenido vida"*, esas casillas también aparecen en gris en el GIF.
- **Contador de fotogramas:** cada fotograma incluye su número superpuesto.
- **Colores fieles:** usa los mismos colores que la interfaz principal.
- **Tamaño correcto:** coincide con el tamaño actual de la cuadrícula y de las celdas.

### **⚙️ Especificaciones técnicas**
- **Máximo de fotogramas:** 300 por grabación.
- **Duración de cada fotograma:** la velocidad de simulación actual, con un mínimo de 100 ms.
- **Formato:** GIF animado estándar con repetición infinita.
- **Gestión de memoria:** los fotogramas se borran tras guardar o cancelar.

### **🔄 Comportamiento inteligente**
- **Reinicio automático:** la grabación se detiene al limpiar la cuadrícula o al cargar un archivo.
- **Estado del botón:** alterna correctamente entre "Grabar GIF" y "Detener grabación".
- **Gestión de errores:** avisa si no se han capturado fotogramas suficientes.

## 🎯 Buenas prácticas

### **📋 Consejos de grabación**
1. **Empieza con algo sencillo:** patrones pequeños e interesantes (parpadeadores, planeadores).
2. **Velocidad óptima:** entre 200 y 500 ms da una buena temporización al GIF.
3. **Planifica los fotogramas:** de 10 a 30 bastan para la mayoría de patrones.
4. **Tamaño de la cuadrícula:** las cuadrículas pequeñas (de 20×20 a 40×40) funcionan mejor.

### **🎨 Patrones sugeridos**
- **Parpadeador (blinker):** línea horizontal de 3 células (oscila cada 2 fotogramas).
- **Planeador (glider):** el patrón móvil clásico (se repite cada 4 fotogramas).
- **Faro (beacon):** dos bloques de 2×2 con un hueco (oscila cada 2 fotogramas).
- **Púlsar:** patrón oscilante grande (periodo 3).

> Estos patrones son los clásicos de Conway. Si cambias las reglas de reproducción en el panel de reglas, su comportamiento puede ser distinto.

### **💾 Gestión de archivos**
- **Nombres:** usa nombres descriptivos, como "planeador_animacion.gif".
- **Tamaño:** suelen ocupar entre 50 KB y 500 KB según el número de fotogramas y el tamaño de la cuadrícula.
- **Para compartir:** ideal para documentación, presentaciones o redes sociales.

## 🛠️ Solución de problemas

**Aparece el aviso "Sin fotogramas"**
- Se necesitan al menos 2 fotogramas para un GIF válido.
- Ejecuta pasos o la simulación continua después de empezar a grabar.

**Archivos demasiado grandes**
- Reduce el tamaño de la cuadrícula.
- Usa menos fotogramas (con 10 a 30 suele bastar).
- Elige patrones con pocas células activas.

**Problemas de memoria**
- La grabación admite un máximo de 300 fotogramas.
- Los fotogramas se borran tras guardar.
- Reinicia la aplicación si el consumo de memoria parece alto.

### **Consejos de rendimiento**
- Cierra otras aplicaciones para grabar con más fluidez.
- Usa velocidades moderadas (100 a 500 ms).
- Evita cuadrículas muy grandes (más de 50×50) al grabar.
- Graba secuencias cortas.

## 🎉 Ejemplos

### **Ejemplo rápido**
1. Abre la interfaz.
2. Dibuja una línea horizontal de 3 células en el centro.
3. Pulsa "Grabar GIF".
4. Pulsa "Paso" 4 o 5 veces para ver oscilar el parpadeador.
5. Pulsa "Detener grabación" y guarda el archivo como "parpadeador.gif".

### **Ejemplo avanzado**
1. Pon la cuadrícula en 30×30.
2. Dibuja un planeador en la esquina superior izquierda.
3. Ajusta la velocidad a 300 ms.
4. Pulsa "Grabar GIF".
5. Pulsa "Iniciar" y deja que se ejecuten de 20 a 30 iteraciones.
6. Pulsa "Parar" para detener la simulación y después "Detener grabación".
7. Guárdalo como "viaje_del_planeador.gif".
