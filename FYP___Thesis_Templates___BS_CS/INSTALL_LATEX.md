# LaTeX Installation Guide for CryptoVolt Thesis

Your thesis project requires XeLaTeX and Biber to build the PDF with proper font support.

## Quick Install (Windows)

### Option 1: Use MiKTeX (Recommended - Easiest)
1. **Download**: Visit https://miktex.org/download
2. **Install**: Download `basic-miktex-x.x-x64.exe` and run it
3. **Complete setup** with default options
4. **Verify installation**:
   ```powershell
   xelatex --version
   biber --version
   ```

### Option 2: Use TeX Live (Alternative)
1. **Download**: Visit https://www.tug.org/texlive/windows.html
2. **Install**: Run the installer and select full installation
3. **Verify installation** (same as above)

## After Installation

Once installed, restart VS Code completely:
```powershell
# Kill VS Code and reopen
```

The VS Code LaTeX Workshop extension will automatically detect the tools and rebuild your PDF on save.

## Verify Build

1. Open `dissertation.tex` in VS Code
2. Save the file (Ctrl+S)
3. Check the build output in **Output panel** (Ctrl+Shift+J)
4. View compiled PDF: Click "View PDF" in editor or open `dissertation.pdf`

## One-command build (Windows, MiKTeX in default location)

From PowerShell in `FYP___Thesis_Templates___BS_CS`:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\compile-dissertation.ps1
```

This runs **xelatex → biber → xelatex → xelatex** and writes `dissertation.pdf`.  
Install MiKTeX first, e.g. `winget install MiKTeX.MiKTeX` (first build may take several minutes while packages download).

## Build Manually (if needed)

From PowerShell in the thesis directory:
```powershell
xelatex -synctex=1 -interaction=nonstopmode dissertation.tex
biber dissertation
xelatex -synctex=1 -interaction=nonstopmode dissertation.tex
xelatex -synctex=1 -interaction=nonstopmode dissertation.tex
```

## Troubleshooting

**PDF still shows old content?**
- Delete `dissertation.pdf`, `dissertation.aux`, `dissertation.bbl` files
- Save `dissertation.tex` again to trigger rebuild

**"Biber not found" error?**
- Check MiKTeX Console (Start Menu > MiKTeX Console > Settings)
- Ensure Biber is installed, not just marked for on-demand installation

**Font errors?**
- Your template uses XeLaTeX to support custom fonts in the `fonts/` folder
- Use `xelatex` not `pdflatex` for proper rendering

## Document Structure

Your thesis is organized as:
- `dissertation.tex` - Master file (DO NOT EDIT content, only metadata)
- `title/title.tex` - Title/committee page
- `summary/summary.tex` - Executive summary
- `acks/acks.tex` - Acknowledgements  
- `chapter/chapter-1.tex` through `chapter-6.tex` - Main content
- `appendix/appendix-*.tex` - Appendices
- `dissertation.bib` - References (BibTeX format)

## Edit Your Content

All chapter files have placeholder text. Replace with your actual content:
1. Open each `chapter/chapter-X.tex` file
2. Expand the sections with your writing
3. Replace figure placeholders with `\includegraphics` commands
4. Add your table data into the LaTeX table environments

The template will handle formatting, citations, and table of contents automatically.
