"""Convert notebook_src.py (`# %%` cell markers) into a clean, output-free Colab notebook."""
import re, sys, pathlib, nbformat

src = pathlib.Path(__file__).with_name("notebook_src.py").read_text()
out = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else
                   pathlib.Path(__file__).parents[1] / "notebook" / "BDMLA_Flight_Delay_Spark.ipynb")

cells = []
for block in re.split(r"^# %%", src, flags=re.M)[1:]:
    header, _, body = block.partition("\n")
    body = body.strip("\n")
    if header.strip() == "[markdown]":
        text = "\n".join(l[2:] if l.startswith("# ") else l.lstrip("#") for l in body.splitlines())
        cells.append(nbformat.v4.new_markdown_cell(text))
    else:
        cells.append(nbformat.v4.new_code_cell(body))

nb = nbformat.v4.new_notebook(cells=cells)
nb.metadata = {"kernelspec": {"name": "python3", "display_name": "Python 3"},
               "language_info": {"name": "python"}, "colab": {"provenance": [], "toc_visible": True}}
nbformat.write(nb, out)
print(f"wrote {out} ({len(cells)} cells)")
