console.log("correcao.js carregado corretamente");

document.addEventListener("DOMContentLoaded", () => {
    let zoom = "fit-width";
    let imagemAtual = null;
    let correcoes = {};

    const imagemPrincipal = document.getElementById("imagem-principal");
    const nomeImagem = document.getElementById("nome-imagem");
    const overlay = document.getElementById("overlay-marcacoes");
    const imageWrapper = document.getElementById("image-wrapper");
    const tipoMarcacao = document.getElementById("tipo-marcacao");
    const zoomSelect = document.getElementById("zoom-select");
    const imageArea = document.getElementById("image-area");
    const btnImagemAnterior = document.getElementById("imagem-anterior");
    const btnProximaImagem = document.getElementById("proxima-imagem");

    async function carregarCorrecoes() {
        try {
            const resposta = await fetch(`/correcoes/${NOME_PROCESSAMENTO}`);
            correcoes = await resposta.json();
        } catch (e) {
            correcoes = {};
        }
    }

    function aplicarZoom() {
        if (!imagemPrincipal || !imagemPrincipal.naturalWidth) return;

        const larguraNatural = imagemPrincipal.naturalWidth;
        const alturaNatural = imagemPrincipal.naturalHeight;

        const larguraDisponivel = Math.max(imageArea.clientWidth - 40, 100);
        const alturaDisponivel = Math.max(imageArea.clientHeight - 40, 100);

        let fatorZoom;

        if (zoom === "fit-width") {
            fatorZoom = larguraDisponivel / larguraNatural;
        } else if (zoom === "fit-window") {
            const fatorLargura = larguraDisponivel / larguraNatural;
            const fatorAltura = alturaDisponivel / alturaNatural;
            fatorZoom = Math.min(fatorLargura, fatorAltura);
        } else {
            fatorZoom = Number(zoom);
        }

        fatorZoom = Math.max(0.12, Math.min(fatorZoom, 3));

        const novaLargura = larguraNatural * fatorZoom;
        const novaAltura = alturaNatural * fatorZoom;

        imagemPrincipal.style.width = `${novaLargura}px`;
        imagemPrincipal.style.height = `${novaAltura}px`;

        imageWrapper.style.width = `${novaLargura}px`;
        imageWrapper.style.height = `${novaAltura}px`;

        ajustarOverlay();
        desenharMarcacoes();
    }

    function ajustarOverlay() {
        if (!imagemPrincipal || !overlay || !imageWrapper) return;

        overlay.style.width = `${imagemPrincipal.clientWidth}px`;
        overlay.style.height = `${imagemPrincipal.clientHeight}px`;
        overlay.style.left = "0px";
        overlay.style.top = "0px";
    }

    function selecionarImagem(nome) {
        if (!nome) {
            console.warn("Nome da imagem vazio.");
            return;
        }

        imagemAtual = nome;
        nomeImagem.textContent = nome;

        const urlImagem = `/imagem/${NOME_PROCESSAMENTO}/${encodeURIComponent(nome)}`;
        console.log("Carregando imagem:", urlImagem);

        imagemPrincipal.src = urlImagem;

        if (!correcoes[imagemAtual]) {
            correcoes[imagemAtual] = [];
        }

        imagemPrincipal.onload = () => {
            console.log("Imagem carregada:", nome);
            zoom = zoomSelect.value || "fit-width";
            aplicarZoom();
        };

        imagemPrincipal.onerror = () => {
            console.error("Erro ao carregar imagem:", urlImagem);
            alert("Erro ao carregar a imagem. Confira se ela existe na pasta debug_omr.");
        };
    }

    function coordenadaNaImagem(event) {
        const rect = overlay.getBoundingClientRect();

        const xTela = event.clientX - rect.left;
        const yTela = event.clientY - rect.top;

        const escalaX = imagemPrincipal.naturalWidth / rect.width;
        const escalaY = imagemPrincipal.naturalHeight / rect.height;

        return {
            x: xTela * escalaX,
            y: yTela * escalaY
        };
    }

    function desenharMarcacoes() {
        overlay.innerHTML = "";

        if (!imagemAtual || !correcoes[imagemAtual]) return;

        const rect = imagemPrincipal.getBoundingClientRect();
        const escalaX = rect.width / imagemPrincipal.naturalWidth;
        const escalaY = rect.height / imagemPrincipal.naturalHeight;

        correcoes[imagemAtual].forEach((marcacao) => {
            const ponto = document.createElement("div");

            ponto.classList.add("marcacao-web");
            ponto.classList.add(marcacao.cor === "vermelho" ? "vermelho" : "verde");

            ponto.style.left = `${marcacao.x * escalaX}px`;
            ponto.style.top = `${marcacao.y * escalaY}px`;

            overlay.appendChild(ponto);
        });
    }

    function adicionarMarcacao(event) {
        if (!imagemAtual) return;

        const coord = coordenadaNaImagem(event);

        correcoes[imagemAtual].push({
            x: coord.x,
            y: coord.y,
            cor: tipoMarcacao.value
        });

        desenharMarcacoes();
    }

    function removerMarcacao(event) {
        if (!imagemAtual) return;

        const coord = coordenadaNaImagem(event);
        const lista = correcoes[imagemAtual] || [];

        if (!lista.length) return;

        let indiceMaisProximo = -1;
        let menorDistancia = Infinity;

        lista.forEach((marcacao, index) => {
            const dx = marcacao.x - coord.x;
            const dy = marcacao.y - coord.y;
            const distancia = Math.sqrt(dx * dx + dy * dy);

            if (distancia < menorDistancia) {
                menorDistancia = distancia;
                indiceMaisProximo = index;
            }
        });

        if (indiceMaisProximo >= 0 && menorDistancia <= 35) {
            lista.splice(indiceMaisProximo, 1);
            desenharMarcacoes();
        }
    }

    document.querySelectorAll(".item-imagem").forEach((botao) => {
        botao.addEventListener("click", () => {
            document.querySelectorAll(".item-imagem").forEach((b) => {
                b.classList.remove("ativo");
            });

            botao.classList.add("ativo");

            const nome = botao.dataset.imagem;
            selecionarImagem(nome);
        });
    });

    overlay?.addEventListener("click", (event) => {
        event.preventDefault();
        event.stopPropagation();
        adicionarMarcacao(event);
    });

    overlay?.addEventListener("contextmenu", (event) => {
        event.preventDefault();
        event.stopPropagation();
        removerMarcacao(event);
        return false;
    });

    imageWrapper?.addEventListener("contextmenu", (event) => {
        event.preventDefault();
        event.stopPropagation();
        removerMarcacao(event);
        return false;
    });

    document.getElementById("zoom-mais")?.addEventListener("click", () => {
        if (zoom === "fit-width" || zoom === "fit-window") {
            zoom = imagemPrincipal.clientWidth / imagemPrincipal.naturalWidth;
        }

        zoom = Math.min(Number(zoom) + 0.1, 3);
        aplicarZoom();
    });

    document.getElementById("zoom-menos")?.addEventListener("click", () => {
        if (zoom === "fit-width" || zoom === "fit-window") {
            zoom = imagemPrincipal.clientWidth / imagemPrincipal.naturalWidth;
        }

        zoom = Math.max(Number(zoom) - 0.1, 0.1);
        aplicarZoom();
    });

    zoomSelect?.addEventListener("change", () => {
        const valor = zoomSelect.value;

        if (valor === "fit-width" || valor === "fit-window") {
            zoom = valor;
        } else {
            zoom = Number(valor);
        }

        aplicarZoom();
    });

    document.getElementById("btn-salvar")?.addEventListener("click", async () => {
        const resposta = await fetch(`/correcoes/${NOME_PROCESSAMENTO}`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                correcoes: correcoes
            })
        });

        if (resposta.ok) {
            alert("Marcações salvas com sucesso.");
        } else {
            alert("Erro ao salvar marcações.");
        }
    });

    

    window.addEventListener("resize", () => {
        ajustarOverlay();
        desenharMarcacoes();
    });

    carregarCorrecoes().then(() => {
        function imagemSelecionadaAtual() {
            return document.querySelector(".item-imagem.ativo");
        }

        function selecionarImagemPorIndice(indice) {
            const botoes = Array.from(document.querySelectorAll(".item-imagem"));

            if (!botoes.length) return;

            if (indice < 0) {
                indice = botoes.length - 1;
            }

            if (indice >= botoes.length) {
                indice = 0;
            }

            botoes[indice].click();
            botoes[indice].scrollIntoView({
                behavior: "smooth",
                block: "nearest"
            });
        }

        function irParaProximaImagem() {
            const botoes = Array.from(document.querySelectorAll(".item-imagem"));
            const atual = imagemSelecionadaAtual();

            if (!botoes.length) return;

            const indiceAtual = botoes.indexOf(atual);
            selecionarImagemPorIndice(indiceAtual + 1);
        }

        function irParaImagemAnterior() {
            const botoes = Array.from(document.querySelectorAll(".item-imagem"));
            const atual = imagemSelecionadaAtual();

            if (!botoes.length) return;

            const indiceAtual = botoes.indexOf(atual);
            selecionarImagemPorIndice(indiceAtual - 1);
        }

        btnProximaImagem?.addEventListener("click", irParaProximaImagem);
        btnImagemAnterior?.addEventListener("click", irParaImagemAnterior);

        document.addEventListener("keydown", (event) => {
            if (event.key === "ArrowRight") {
                irParaProximaImagem();
            }

            if (event.key === "ArrowLeft") {
                irParaImagemAnterior();
            }
        });
        const primeiroBotao = document.querySelector(".item-imagem");

        if (primeiroBotao) {
            primeiroBotao.click();
        } else {
            console.warn("Nenhuma imagem encontrada na lista.");
        }
    });
});
