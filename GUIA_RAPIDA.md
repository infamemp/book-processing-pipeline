# Guía rápida: de un libro a su KB

## Una sola vez
1. Instala Python y abre PowerShell en la carpeta del repo.
2. `pip install -r requirements.txt`
3. Confirma las variables `ANTHROPIC_API_KEY` y `GEMINI_API_KEY` (Windows → Variables de entorno).
4. Verifica que la cuenta de Anthropic tenga saldo.

## Cada libro
1. **Actualiza el repo:** GitHub Desktop → Fetch origin → Pull.
2. **Deja el libro** (.epub o .pdf) en cualquier carpeta, por ejemplo Descargas.
3. **Corre** (elige uno):
   ```powershell
   .\procesar_libro.ps1 -Libro "E:\Descargas\mi-libro.epub" -Lote     # barato
   .\procesar_libro.ps1 -Libro "E:\Descargas\mi-libro.epub"           # inmediato
   ```
4. **Lee el costo estimado** y responde `s` para continuar (o `n` para cancelar sin gastar).
5. **Si usaste `-Lote`:** espera unos minutos u horas y vuelve a correr **el mismo comando**. Repítelo hasta que aparezca el bloque final con CORE / BIBLIOTECA / Reporte.
6. **Si algo se detiene o da error:** corre el mismo comando otra vez. No repite lo ya pagado.
7. **Revisa** `_reporte.txt`: la sección AVISOS lista números que no aparecen en el capítulo (pueden ser valores derivados legítimos).
8. **Usa los archivos** de `Library\<libro>\`: `_core.md`, `_biblioteca.md` y `_indice.json`.

## Prueba barata (opcional)
Solo dos capítulos: agrega `-Unidades "U05,U08"`. Sale un KB parcial, sin síntesis.

## Problemas comunes
- **"Your credit balance is too low":** recarga saldo en la consola de Anthropic y repite el comando.
- **"Falta la variable de entorno":** define la variable y abre PowerShell de nuevo.
- **Un PDF escaneado:** la conversión usa Gemini; revisa `libro.conversion_report.txt` antes de extraer.
