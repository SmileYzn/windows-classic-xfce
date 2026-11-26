## Windows Classic Theme para XFCE

# Sobre
Vou criar nessa pasta um tema completo para XFCE:
O tema deverá ser idêntico ao possível ao Tema clássico do Windows XP.

Responder sempre em português do Brasil.
Comentários de scripts e READMEs também em pt-BR.

# Passo a passo do projeto:
As pastas do projeto e os passos:

1. Cursors
   - Nome da pasta: windows-classic-cursors
   - Tema de cursores (Para X11)
2. Theme:
   - Nome da pasta: windows-classic
   - xfwm4
   - gtk-3.0
3. Icons:
   - Nome da pasta: windows-classic-icons
   - Tema de ícones (padrão freedesktop)

# GitHub
Repositório do projeto:
 - https://github.com/smileyzn/windows-classic-xfce

# Referências
Há alguns temas em GTK semelhantes em:

https://github.com/pixelocdguy/windows-classic
https://github.com/rozniak/xfce-winxp-tc
https://github.com/SmileYzn/win2k/tree/main/Theme/Win2k

# Arquivos do Windows XP
Posso indicar onde está a pasta I386 da instalação original do Windows XP

# Testes locais
Os testes podem ser feitos com a melhor ferramenta disponível.
Quando terminar um passo do projeto, abra uma sessão de testes com Xephyr

# Ferramentas
Qualquer ferramenta que precisar para instalação no Arch Linux, me mostre como posso intalar.

# Guia de design do Windows XP (GUI_Xp.pdf)
O arquivo `GUI_Xp.pdf` (na raiz do projeto) é o "Windows XP Visual Guidelines" (Microsoft, 2001).
**Sempre que criar ou alterar qualquer coisa (ícones, tema GTK, xfwm4, cursores, painel...), siga esse guia.**
Texto extraído para consulta: `pdftotext -layout GUI_Xp.pdf -` (seções: Fonts, Colors, Icons, Controls, Folders & Layouts).

Resumo do que vale para o projeto:
- Quatro adjetivos: fresco, desejável, colorido e simples. Cores ricas, curvas suaves, gradientes sutis.
- Fontes: Tahoma é a padrão (8, 9 ou 11 pt); Trebuchet MS Bold 10 pt só no título das janelas;
  Verdana Bold 8 pt só em títulos de paletas flutuantes; Franklin Gothic só acima de 14 pt, nunca em texto corrido.
- Paleta (hex) no capítulo Colors do PDF, ex.: azul #0046D5/#316AC5/#003399, verde #22C020/#13920D, vermelho #DE5C2F, amarelo #FFCC00, laranja #FF9933.
- Ícones no estilo XP: cores ricas; ângulo e perspectiva (documentos, símbolos e objetos únicos ficam de frente);
  bordas e cantos suaves e levemente arredondados; luz vinda do canto superior esquerdo, com luz ambiente;
  gradientes; sombra projetada (ângulo 135°, distância 2, tamanho 2, preta a 75%); contorno para dar definição;
  no máximo 3 objetos por ícone; sem letras, palavras, mãos ou rostos; simplificar no tamanho 16x16.
- Tamanhos de ícone: 48, 32, 24 e 16 px (barras de ferramentas: 24 e 16, estados normal e "hot").
- Notas do projeto: a tela de destino é o tema **clássico** (cinza); onde o guia (Luna) e o tema clássico divergirem em controles,
  vale o clássico, mas ícones e imagens seguem o estilo XP do guia.
