import pdfplumber

RUTA_DE_DOCUMENTO = "ThinkPython.pdf"
PAGINA_INICIAL = 20


def tabla(pares):
    t = {}
    for cifrado, claro in pares:
        if len(cifrado) != len(claro):
            raise ValueError(
                "descuadre:\n  %s (%d)\n  %s (%d)"
                % (cifrado, len(cifrado), claro, len(claro))
            )
        t.update(dict(zip(cifrado, claro)))

    return t


def traducir(texto, ta):

    p = []
    for c in texto:
        txt = ta.get(c, c)
        p.append(txt)

    return "".join(p)


ta = tabla(
    [
        ("❛♥❞ ❞❡❧ ❢r♦♠ ♥♦t ✇❤✐❧❡", "and del from not while"),
        ("❛s ❡❧✐❢ ❣❧♦❜❛❧ ♦r ✇✐t❤", "as elif global or with"),
        ("❛ss❡rt ❡❧s❡ ✐❢ ♣❛ss ②✐❡❧❞", "assert else if pass yield"),
        ("❜r❡❛❦ ❡①❝❡♣t ✐♠♣♦rt ♣r✐♥t", "break except import print"),
        ("❝❧❛ss ❡①❡❝ ✐♥ r❛✐s❡", "class exec in raise"),
        ("❝♦♥t✐♥✉❡ ❢✐♥❛❧❧② ✐s r❡t✉r♥", "continue finally is return"),
        ("❞❡❢ ❢♦r ❧❛♠❜❞❛ tr②", "def for lambda try"),
        ("❃❃❃ ✶✱✵✵✵✱✵✵✵", ">>> 1,000,000"),
        ("❃❃❃ ✼✻tr♦♠❜♦♥❡s ❂ ❜✐❣ ♣❛r❛❞❡", ">>> 76trombones = big parade"),
        ("❙②♥t❛①❊rr♦r✿ ✐♥✈❛❧✐❞ s②♥t❛①", "SyntaxError: invalid syntax"),
        ("❃❃❃ ♠♦r❡❅ ❂ ✶✵✵✵✵✵✵", ">>> more@ = 1000000"),
        (
            "❃❃❃ ❝❧❛ss ❂ ❆❞✈❛♥❝❡❞ ❚❤❡♦r❡t✐❝❛❧ ❩②♠✉r❣②",
            ">>> class = Advanced Theoretical Zymurgy",
        ),
        (
            "✷✵✰✸✷ ❤♦✉r✲✶ ❤♦✉r✯✻✵✰♠✐♥✉t❡ ♠✐♥✉t❡✴✻✵ ✺✯✯✷ ✭✺✰✾✮✯✭✶✺✲✼✮",
            "20+32 hour-1 hour*60+minute minute/60 5**2 (5+9)*(15-7)",
        ),
        (
            "❤tt♣✿✴✴✇✐❦✐✳♣②t❤♦♥✳♦r❣✴♠♦✐♥✴❇✐t✇✐s❡❖♣❡r❛t♦rs✳",
            "http://wiki.python.org/moin/BitwiseOperators.",
        ),
        ("✬❫❴", "'^_"),
        # el libro trae una linea con toda la puntuacion ascii seguida:
        #   !"#$%& ()*+,-./:;<=>?@[\]^_ `{|}~
        ("✦✧★✩✪✫❀❁❄❬❭❪❵④⑤⑥⑦", '!"#$%&;<?[\\]`{|}~'),
        # mayusculas, sacadas de los mensajes de error y de la lista de
        # prefijos JKLMNOPQ del capitulo de cadenas
        ("❋■◆❈▲❉❲❘❍▼●❏❑◗❱❨❯❳③❥✹✽", "FINCLDWRHMGJKQVYUXzj48"),
    ]
)


def main():
    pendientes = set()

    with pdfplumber.open(RUTA_DE_DOCUMENTO) as r:
        for page in r.pages[PAGINA_INICIAL:]:
            lineas = page.extract_text_lines(x_tolerance=1.5)
            for linea in lineas:
                for c in traducir(linea["text"], ta):
                    if not c.isascii():
                        pendientes.add(c)

    print("faltan", len(pendientes), ":", "".join(sorted(pendientes)))


if __name__ == "__main__":
    main()
