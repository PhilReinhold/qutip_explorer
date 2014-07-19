import os
import subprocess
import tempfile


def save_latex(filename, contents):
    tex = r"""
\documentclass[fleqn]{article}
\usepackage{amsmath}
\usepackage{color}
\usepackage{bm}
\usepackage[active,tightpage,displaymath]{preview}
\renewcommand \PreviewBbAdjust {0.0bp -\PreviewBorder 70.0bp 8.0bp}
\usepackage[customcolors]{hf-tikz}
\begin{document}
%s
\end{document}
""" % contents
    print tex
    cwd = os.getcwd()
    #os.chdir(r"C:\Users\rsl\AppData\Local\Temp")
    if os.path.exists(filename):
        os.remove(filename)
    f = tempfile.NamedTemporaryFile(delete=False, suffix=".tex")
    f.write(tex)
    f.close()
    tempdir = os.path.dirname(f.name)
    try:
        subprocess.check_call([
            "latex", "-interaction=nonstopmode",
            "-output-directory="+tempdir, f.name
        ])
        subprocess.check_call([
            "pdflatex", "-interaction=nonstopmode",
            "-output-directory="+tempdir, f.name
        ])
    finally:
        os.remove(f.name)
    pdfname = f.name.replace("tex", "pdf")
    pngname = f.name.replace("tex", "png")

    try:
        #cmd = r"dvipng -picky -noghostscript -bg Transparent -D 480 -v " + dviname
        #cmd = r"dvipng -picky -bg Transparent -D 480 -v " + dviname
        def cygwinify(path):
            return ("/cygdrive/%s%s" % tuple(path.split(":"))).lower().replace('\\','/')

        #cmd = r'C:\cygwin64\bin\bash.exe -c "/usr/bin/convert -density 480 %s %s"' % (cygwinify(pdfname), cygwinify(pngname))
        cmd = [r'C:\cygwin64\bin\bash.exe',  '-lc', 'convert -density 480 %s %s' % (cygwinify(pdfname), cygwinify(pngname))]
        print subprocess.list2cmdline(cmd)
        subprocess.check_call(cmd, shell=True)
        #print cmd
        #import shlex
        #print shlex.split(cmd, posix=False)
        #print subprocess.list2cmdline(shlex.split(cmd, posix=False))
        #subprocess.check_call(shlex.split(cmd, posix=False), shell=True)
    finally:
        os.remove(pdfname)
    print pngname, filename
    os.rename(pngname, filename)
    os.chdir(cwd)



def make_images():
    params = {
        "leg_count": "m_j",
        "init_state": r"|n_j\rangle",
        "leg_phase": r"\phi_{jk}",
        "displacement": r"\alpha_i",
        "pulse": r"\mathcal{E}(t)",
    }
    components = (
    )

    eqns = {
        "hamiltonian":
            (r"\mathcal{H} = %s + %s + %s",
             {"freq": r"\omega_j",
              "kerr": "K_{jk}",
              "drive_amp": r"\lambda_j",
              "drive_phase": r"\theta_j"},
             ((r"\sum_j %(freq)s a_j^\dagger a_j", ["freq"]),
              (r"\sum_{j,k} %(kerr)sa_j^\dagger a_k^\dagger a_k a_j", ["kerr"]),
              (r"%(pulse)s\sum_j %(drive_amp)s(e^{-i%(drive_phase)s}a_j + e^{i%(drive_phase)s}a_j^\dagger)",
               ["pulse", "drive_amp", "drive_phase"]))),
        "pulse":
            (r"\mathcal{E}(t) = %s + %s",
             {
                 "iquad": r"\mathcal{I}",
                 "qquad": r"\mathcal{Q}",
                 "drive_freq": r"\omega_\text{drive}",
                 "drive_phase": r"\omega_\text{drive}",
             },
             (("(iquad)s\cos(%(drive_freq)s + (drive_phase)s)s t)", ["iquad", "drive_freq", "drive_phase"]),
              ("(qquad)s\sin(%(drive_freq)s + (drive_phase)s)s t)", ["qquad", "drive_freq", "drive_phase"]))),
        "lindblad":
            (r"\dot{\rho} = \left[\mathcal{H}, \rho\right] + %s + %s",
             {"decay": r"\kappa_j",
              "dephasing": r"\gamma_j"},
             ((r"\sum_j%(decay)s\mathcal{D}\left[a_j\right]", ["decay"]),
              (r"\sum_j%(dephasing)s\mathcal{D}\left[a_j^\dagger a_j\right]", ["dephasing"]))),
        "initial":
            (r"\psi_0 = %s\;\;\; \beta_{jk} = %s",
             ((r"\bigotimes_j \sum_k^{%(leg_count)s} e^{i%(leg_phase)s} D_{\beta_{jk}}%(init_state)s",
               ["leg_count", "leg_phase", "init_state"]),
                 (r"e^{2\pi i \frac{k}{%(leg_count)s}} %(displacement)s",
                  ["leg_count", "displacement"])
             )),
    }

    latex_tmpl = r"""
    \hfsetfillcolor{blue!10}
    \hfsetbordercolor{blue}
    \begin{gather*}
    %s
    \end{gather*}
    """

    path = os.path.join(os.getcwd(), "latex", "eqn%s.png")
    #save_latex(path % "", (tmpl % tuple([c for c, _ in components])) % params)
    for eq_name in eqns:
        eq_tmpl, params_dict, blocks = eqns[eq_name]
        for param_name, param_str in params_dict.items():
            params_dict_copy = params_dict.copy()
            params_dict_copy[param_name] = r"{\color{red}\bm{%s}}"
            formatted_blocks = []
            for i, (block_str, block_params) in enumerate(blocks):
                if param_name in block_params:
                    formatted_blocks.append(
                        r"\tikzmarkin{%d}(0.1,-0.5)(-0.2,0.6)%s\tikzmarkend{%d}" % (i, block_str, i)
                    )
                else:
                    formatted_blocks.append(block_str)
            name = "_" + eq_name + "_" + param_name
            latex_str = (((latex_tmpl % eq_tmpl) % tuple(formatted_blocks)) % params_dict_copy)
            save_latex(path % name, latex_str)


    for name in params:
        components_copy = []
        for i, (c, name_list) in enumerate(components):
            if name in name_list:
                components_copy.append(
                    r"\tikzmarkin{%d}(0.1,-0.5)(-0.2,0.6)%s\tikzmarkend{%d}" % (i, c, i)
                )
            else:
                components_copy.append(c)


        filled_tmpl = tmpl % tuple(components_copy)
        params_copy = params.copy()
        params_copy[name] = r"{\color{red}\bm{%s}}" % params[name]
        print filled_tmpl % params_copy
        save_latex(path % ("_"+name), filled_tmpl % params_copy)

if __name__ == '__main__':
    make_images()
