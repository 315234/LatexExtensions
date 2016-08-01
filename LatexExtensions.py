import sublime
import sublime_plugin

import urllib.parse
import urllib.request
from base64 import b64encode
import plistlib
import re
import os
import sys


#!/usr/bin/python
import os
import sys
import subprocess
import tempfile
import base64

LATEX_SCOPE="meta.environment.math"

# Try to render the given latex snippet with the given preamble as a png.
# If successful, return a png image encoded as a base64 string.
# Otherwise return None.
def render_latex(content, preamble, pdflatex="pdflatex", convert="convert", pdfcrop="pdfcrop"):
    # Create a temporary directory to do all the work in, which will be automatically deleted
    tmpdir = tempfile.TemporaryDirectory()
    tmptex = os.path.join(tmpdir.name, "LatexExtensions_tmp_output_file.tex")
    tmppdf = os.path.join(tmpdir.name, "LatexExtensions_tmp_output_file.pdf")
    tmppdf_crop = os.path.join(tmpdir.name, "LatexExtensions_tmp_output_file-crop.pdf")
    tmppng = os.path.join(tmpdir.name, "LatexExtensions_tmp_output_file.png")

    # Construct whole document from preamble and content
    wholedoc =  ( r'\documentclass[preview]{standalone}' + os.linesep
                  + preamble                             + os.linesep
                  + r'\begin{document}'                  + os.linesep
                  + content                              + os.linesep
                  + r'\end{document}'                    + os.linesep )

    # Write temporary latex file to disk
    with open(tmptex, "w", encoding="utf-8") as f:
        f.write(wholedoc)

    # Run pdflatex to product pdf
    try:
        r = subprocess.check_output([pdflatex, tmptex], cwd=tmpdir.name, stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError as e:
        print("LatexExtensions: pdflatex error: ", e)
        print("LatexExtensions: pdflatex output: ")
        print(e.output.decode())
    if not os.path.isfile(tmppdf):
        print("file does not exist: "+tmppdf)
        return None

    # Run pdfcrop to remove extra whitespace around equation
    try:
        pdftex = pdflatex.replace("pdflatex", "pdftex")
        r = subprocess.check_output([pdfcrop, tmppdf, "--pdftexcmd", pdftex], cwd=tmpdir.name, stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError as e:
        print("LatexExtensions: pdfcrop error: ", e)
        print("LatexExtensions: pdfcrop output: ")
        print(e.output.decode())
    if not os.path.isfile(tmppdf_crop):
        print("file does not exist: "+tmppdf_crop)
        return None


    # Run convert to product png
    r = subprocess.check_output([convert, "-density", "200x200", tmppdf_crop, tmppng], cwd=tmpdir.name)
    if not os.path.isfile(tmppng):
        print("file does not exist: "+tmppng)
        return None

    # Read the png and store in a base64 encoded string
    with open(tmppng, "rb") as f:
        rawdata = f.read()
        imgdata = base64.b64encode(rawdata).decode()
        return imgdata

    # If we got to here, something bad happened
    print("LatexExtensions: unknown error")
    return None

class LatexHeaderPhantoms(sublime_plugin.ViewEventListener):
    def __init__(self, view):
        self.view = view
        self.phantom_set = sublime.PhantomSet(view)
        self.timeout_scheduled = False
        self.needs_update = False

        self.update_phantoms()

    @classmethod
    def is_applicable(cls, settings):
        return "LaTeX" in settings.get('syntax')

    def update_phantoms(self):
        phantoms = []
        notere = r"%§"
        secre = r"\\((?:sub)*section|chapter|part)\{"
        todore = r"\\(todo(\[inline\])?)\{"
        graphicsre = r"\\includegraphics\{"
        if self.view.size() < 2**20:
            for tagregion in self.view.find_all(notere):
                line_region = self.view.line(tagregion.a)
                line = self.view.substr(line_region)
                text = line[2:]
                mode = "warning"
                tag = "h3"
                html_str = '<{} class="{}">{}</{}>'.format(tag, mode, text, tag)
                insert_region = sublime.Region(line_region.b, line_region.b)
                phantoms.append(sublime.Phantom(insert_region, html_str, sublime.LAYOUT_BLOCK))
            for tagregion in self.view.find_all(secre):
                line_region = self.view.line(tagregion.a)
                line = self.view.substr(line_region)
                match = re.match(secre, line)
                if match:
                    text = line
                    text = re.sub(secre, '', text)
                    text = re.sub(r'\}.*', '', text)
                    mode = "success"

                    if match.group(1) in ["section", "chapter", "part"]:
                        tag = "h1"
                        if match.group(1) in ["chapter", "part"]:
                            mode = "error"
                    elif match.group(1) == "subsection":
                        tag = "h2"
                    elif match.group(1) == "subsubsection":
                        tag = "h3"
                    else:
                        tag = "span"
                    html_str = '<{} class="{}">{}</{}>'.format(tag, mode, text, tag)
                    insert_region = sublime.Region(line_region.b, line_region.b)
                    phantoms.append(sublime.Phantom(insert_region, html_str, sublime.LAYOUT_BLOCK))
            for tagregion in self.view.find_all(todore):
                line_region = self.view.line(tagregion.a)
                line = self.view.substr(line_region)
                match = re.match(todore, line)
                if match:
                    text = line
                    text = re.sub(todore, '', text)
                    text = re.sub(r'\}.*', '', text)
                    text = "[{}]".format(text)

                    tag = "h2"
                    mode = "error"
                    html_str = '<{} class="{}">{}</{}>'.format(tag, mode, text, tag)
                    insert_region = sublime.Region(line_region.b, line_region.b)
                    phantoms.append(sublime.Phantom(insert_region, html_str, sublime.LAYOUT_BLOCK))
            for tagregion in self.view.find_all(graphicsre):
                line_region = self.view.line(tagregion.a)
                line = self.view.substr(line_region)
                match = re.match(graphicsre, line)
                if match:
                    text = line
                    text = re.sub(graphicsre, '', text)
                    text = re.sub(r'\}.*', '', text)

                    pngfilename = text
                    if os.path.isfile(pngfilename + ".png"):
                        pngfilename = pngfilename + ".png"
                    if os.path.isfile(pngfilename + ".pdf"):
                        pdffilename = pngfilename + ".pdf"
                        pngfilename = os.path.expanduser("~/tmp.png")
                        os.system("gs -q -dSAFER  -sDEVICE=png16m -r150 -dBATCH -dNOPAUSE  -dFirstPage=1 -dLastPage=1 -sOutputFile={} {}".format(pngfilename, pdffilename))
                    with open(pngfilename, "rb") as f:
                        rawdata = f.read()
                        imgdata = b64encode(rawdata).decode()
                        html_str =  '<img src="data:image/png;base64,%s" />' % imgdata
                        insert_region = sublime.Region(line_region.b, line_region.b)
                        phantoms.append(sublime.Phantom(insert_region, html_str, sublime.LAYOUT_BLOCK))
        self.phantom_set.update(phantoms)

    def end_timeout(self):
        self.timeout_scheduled = False
        if self.needs_update:
            self.needs_update = False
            self.update_phantoms()

    def on_modified_async(self):
        # Call update_phantoms(), but not any more than 10 times a second
        if self.timeout_scheduled:
            self.needs_update = True
        else:
            self.update_phantoms()
            self.timeout_scheduled = True
            sublime.set_timeout(lambda: self.end_timeout(), 1000)











class InlineLatexHover(sublime_plugin.EventListener):
    def on_hover(self, view, point, hover_zone):
        if "LaTeX" not in view.settings().get('syntax'):
            return
        if hover_zone != sublime.HOVER_TEXT:
            return
        scope = view.scope_name(point)
        score = sublime.score_selector(scope, LATEX_SCOPE)
        if score > 0:
            # We are hovering over some embedded latex
            region = InlineLatexHover.extract_inline_latex_scope(view, point)
            latex = view.substr(region)
            latex = InlineLatexHover.unicode_sanitise(latex)
            latex = latex.strip()
            if not latex.startswith("$"):
                latex = "$"+latex+"$"

            if len(latex) > 200:
                html_str = '<span class="error">Latex must be 200 characters max<span/>'
            else:
                # bg, fg = 'ffffff', '222222'
                bg, fg = InlineLatexHover.get_colors(view)

                params = urllib.parse.urlencode({'cht': "tx", 'chl': latex, 'chf': 'bg,s,'+bg, 'chco': fg})
                imgurl = "http://chart.googleapis.com/chart?"+params
                try:
                    response = urllib.request.urlopen(imgurl)
                    rawdata = response.read()
                    imgdata = b64encode(rawdata).decode()
                    html_str =  '<img src="data:image/png;base64,%s" />' % imgdata
                except (urllib.error.HTTPError) as e:
                    html_str =  '<span class="error">%s<span/>' % str(e)

            if view.settings().has("latexextensions_latex_preamble"):
                preamble = view.settings().get("latexextensions_latex_preamble")
            elif view.settings().has("latexextensions_latex_preamble_file"):
                preamble_filename = view.settings().get("latexextensions_latex_preamble_file")
                preamble_filename = os.path.expanduser(preamble_filename)
                with open(preamble_filename, "r", encoding="utf-8") as f:
                    preamble = f.read()
            else:
                preamble =  ( r'\usepackage{amsmath}'     + os.linesep +
                              r'\usepackage{amsfonts}'    + os.linesep +
                              r'\usepackage{amssymb}'     + os.linesep )
            pdflatex = view.settings().get("latexextensions_pdflatex_location", "pdflatex")
            pdfcrop = view.settings().get("latexextensions_pdfcrop_location", "pdfcrop")
            convert = view.settings().get("latexextensions_convert_location", "convert")
            pngdata = render_latex(latex, preamble, pdflatex=pdflatex, convert=convert, pdfcrop=pdfcrop)
            if pngdata != None:
                html_str =  '<img src="data:image/png;base64,%s" />' % pngdata
            else:
                html_str =  '<span class="error">Latex rendering error. See console.<span/>'

            view.show_popup(html_str, sublime.HIDE_ON_MOUSE_MOVE_AWAY, point, 1000, 1000)

    @staticmethod
    def extract_inline_latex_scope(view, point):
        """Like extract_scope(), but extracts the extent of scope."""
        istart = point
        iend = point
        while istart > 0 and sublime.score_selector(view.scope_name(istart-1), LATEX_SCOPE) > 0:
            istart = istart - 1
        while iend < view.size() and sublime.score_selector(view.scope_name(iend), LATEX_SCOPE) > 0:
            iend = iend + 1
        r = sublime.Region(istart, iend)
        if r.size() > 1000:
            r = sublime.Region(point, point)
        return r

    @staticmethod
    def unicode_sanitise(latex):
        chars = {
            "α": r"\alpha{}", "β": r"\beta{}", "χ": r"\chi{}", "δ": r"\delta{}", "ε": r"\epsilon{}",
            "ϕ": r"\phi{}", "γ": r"\gamma{}", "η": r"\eta{}", "ι": r"\iota{}", "∆": r"\Delta{}",
            "κ": r"\kappa{}", "λ": r"\lambda{}", "μ": r"\mu{}", "ν": r"\nu{}", "ω": r"\omega{}",
            "π": r"\pi{}", "∂": r"\partial{}", "ρ": r"\rho{}", "σ": r"\sigma{}", "τ": r"\tau{}",
            "θ": r"\theta{}", "ξ": r"\xi{}", "ψ": r"\psi{}", "ζ": r"\zeta{}",
            }
        output = ""
        for c in latex:
            if c in chars:
                output += chars[c]
            else:
                output += c
        return output

    @staticmethod
    def get_colors(view):
        # Code left here for reference
        # scheme_data is a top level dict for the color scheme
        # It has keys "author", "name", "settings" etc.
        # scheme_data["settings"] contains a list of dicts matching "scope" to "settings".
        # It also has one dict with just "settings", which has non-scope related settings (typically first in list)
        # To get color scheme for a particular scope, find the dict with the scope that matches best.
        scheme_path = view.settings().get("color_scheme")
        scheme_content = sublime.load_binary_resource(scheme_path)
        scheme_data = plistlib.readPlistFromBytes(scheme_content)

        def parse_popupCss(css):
            words = css.split()
            i = 0
            bg = None
            fg = None
            while words[i] != "html":
                i += 1
            while words[i] != "}":
                if words[i] == "background-color:":
                    bg = words[i+1]
                if words[i] == "color:":
                    fg = words[i+1]
                i += 1

            # Defaults if not found
            if bg == None:
                bg = "#FFFFFF"
            if fg == None:
                fg = "#000000"

            # Remove leading # and trailing ;
            bg = bg[1:7]
            fg = fg[1:7]
            return bg, fg

        try:
            # Get colors from popupCss
            css = scheme_data["settings"][0]["settings"]["popupCss"]
            bg, fg = parse_popupCss(css)
        except KeyError:
            try:
                # Get colors from the main section of scheme_data["settings"]
                bg = scheme_data["settings"][0]["settings"]["background"][1:]
                fg = scheme_data["settings"][0]["settings"]["foreground"][1:]
            except KeyError:
                bg = "000000"
                fg = "FFFFFF"

        # # theme_datas contains a list of lists of dicts with theme properties.
        # # Each item in the top-level list represents a resource,
        # # i.e. the original theme file, theme addons, user modifications, etc in resource order
        # # I guess we want the last one? theme_data = theme_datas[-1]
        # # theme_data is a list of dicts with keys:
        # #   "class": "tab_control", "icon_button_control", etc
        # #   "attributes": "right", "dirty", "selected" etc
        # #   "layer3.opacity": 0.75 etc
        # #   "settings": [list of settings that are set to true for this to be applied]
        # theme_filename = sublime.load_settings("Preferences.sublime-settings").get("theme")
        # theme_paths = sublime.find_resources(theme_filename)
        # theme_contents = [sublime.load_resource(x) for x in theme_paths]
        # theme_datas = [sublime.decode_value(x) for x in theme_contents]
        # theme_data = theme_datas[-1]

        return (bg, fg)


