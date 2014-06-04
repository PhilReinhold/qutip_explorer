import os
import subprocess
import tempfile


def save_latex(filename, contents):
    tex = r"""
\documentclass[fleqn]{article}
\usepackage{amsmath}
\usepackage{color}
\usepackage[active,tightpage,displaymath]{preview}
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
    finally:
        os.remove(f.name)
    dviname = f.name.replace("tex", "dvi")

    try:
        cmd = r"dvipng -picky -noghostscript -bg Transparent -D 480 -v " + dviname
        print cmd
        import shlex
        print shlex.split(cmd, posix=False)
        print subprocess.list2cmdline(shlex.split(cmd, posix=False))
        subprocess.check_call(shlex.split(cmd, posix=False), shell=True)
    finally:
        os.remove(dviname)
    pngname = os.path.join(os.getcwd(), os.path.basename(dviname).replace(".dvi", "1.png"))
    print pngname, filename
    os.rename(pngname, filename)
    os.chdir(cwd)



def make_images():
    params = {
        "freq": r"\omega_j",
        "kerr": "K_{jk}",
        "drive_amp": r"\lambda_j",
        "drive_phase": r"\theta_j",
        "decay": r"\kappa_j",
        "dephasing": r"\gamma_j",
        "leg_count": "m_j",
        "init_state": r"|n_j\rangle",
        "leg_phase": r"\phi_{jk}",
        "displacement": r"\alpha_i",
        "pulse": r"\mathcal{E}(t)",
    }
    tmpl = r"""
\begin{gather*}
\mathcal{H} = \sum_j %(freq)s a_j^\dagger a_j +
\sum_{j,k} %(kerr)sa_j^\dagger a_k^\dagger a_k a_j +
%(pulse)s\sum_j %(drive_amp)s
(e^{-i%(drive_phase)s}a_j + e^{i%(drive_phase)s}a_j^\dagger)\\
\dot{\rho} = \left[\mathcal{H}, \rho\right] +
\sum_j%(decay)s\mathcal{D}\left[a_j\right]  +
%(dephasing)s\mathcal{D}\left[a_j^\dagger a_j\right]\;\;\;
\psi_0 = \bigotimes_j \sum_k^{%(leg_count)s} e^{i%(leg_phase)s}
D_{\beta_{jk}}%(init_state)s\;\;\;
\beta_{jk} = e^{2\pi i \frac{k}{%(leg_count)s}} %(displacement)s
\end{gather*}
"""
    path = os.path.join(os.getcwd(), "latex", "eqn%s.png")
    save_latex(path % "", tmpl % params)
    for name in params:
        params_copy = params.copy()
        params_copy[name] = "{\color{red}%s}" % params[name]
        save_latex(path % ("_"+name), tmpl % params_copy)

if __name__ == '__main__':
    make_images()
