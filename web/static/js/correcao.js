document.addEventListener("DOMContentLoaded", () => {
    let zoom = "fit-width";
    let imagemAtual = null;
    let correcoes = {};
    let leituras = {};
    let cantosEdicao = {};
    let modoEdicao = "marcacoes";
    let cantoSelecionado = "TOP_LEFT";

    const ORDEM_CANTOS = ["TOP_LEFT", "TOP_RIGHT", "BOTTOM_LEFT", "BOTTOM_RIGHT"];
    const ROTULOS_CANTOS = {
        TOP_LEFT: "canto superior esquerdo",
        TOP_RIGHT: "canto superior direito",
        BOTTOM_LEFT: "canto inferior esquerdo",
        BOTTOM_RIGHT: "canto inferior direito"
    };
    const ABREVIACOES_CANTOS = {
        TOP_LEFT: "SE",
        TOP_RIGHT: "SD",
        BOTTOM_LEFT: "IE",
        BOTTOM_RIGHT: "ID"
    };

    const imagemPrincipal = document.getElementById("imagem-principal");
    const nomeImagem = document.getElementById("nome-imagem");
    const viewerHelp = document.getElementById("viewer-help");
    const overlay = document.getElementById("overlay-marcacoes");
    const imageWrapper = document.getElementById("image-wrapper");
    const tipoMarcacao = document.getElementById("tipo-marcacao-viewer");
    const zoomSelect = document.getElementById("zoom-select");
    const imageArea = document.getElementById("image-area");
    const btnImagemAnterior = document.getElementById("imagem-anterior");
    const btnProximaImagem = document.getElementById("proxima-imagem");
    const modoEdicaoSelect = document.getElementById("modo-edicao");
    const btnReprocessarImagem = document.getElementById("reprocessar-imagem");
    const markerToolbarGroup = document.getElementById("marker-toolbar-group");
    const cornerPillsGroup = document.getElementById("corner-pills-group");
    const toastStack = document.getElementById("toast-stack");
    const botoesCanto = Array.from(document.querySelectorAll(".corner-btn"));

    function mostrarToast(mensagem, tipo = "success", titulo = "") {
        if (!toastStack) {
            return;
        }

        const titulos = {
            success: titulo || "Tudo certo",
            error: titulo || "Algo deu errado",
            warning: titulo || "Atenção"
        };
        const icones = {
            success: "✓",
            error: "!",
            warning: "i"
        };

        const toast = document.createElement("div");
        toast.className = `toast ${tipo}`;

        toast.innerHTML = `
            <span class="toast-icon">${icones[tipo] || "i"}</span>
            <div class="toast-body">
                <strong class="toast-title">${titulos[tipo] || "Aviso"}</strong>
                <p class="toast-message">${mensagem}</p>
            </div>
            <button class="toast-close" type="button" aria-label="Fechar aviso">×</button>
        `;

        const removerToast = () => {
            toast.classList.remove("show");
            window.setTimeout(() => toast.remove(), 220);
        };

        toast.querySelector(".toast-close")?.addEventListener("click", removerToast);
        toastStack.appendChild(toast);

        window.requestAnimationFrame(() => {
            toast.classList.add("show");
        });

        window.setTimeout(removerToast, 3600);
    }

    async function carregarCorrecoes() {
        try {
            const resposta = await fetch(`/correcoes/${NOME_PROCESSAMENTO}`);
            correcoes = await resposta.json();
        } catch (e) {
            correcoes = {};
        }
    }

    async function carregarLeituras() {
        try {
            const resposta = await fetch(`/leituras/${NOME_PROCESSAMENTO}`);
            leituras = await resposta.json();
        } catch (e) {
            leituras = {};
        }
    }

    function normalizarCantosLidos(pontos) {
        if (!pontos) {
            return {};
        }

        if (Array.isArray(pontos) && pontos.length === 4) {
            return {
                TOP_LEFT: pontos[0],
                TOP_RIGHT: pontos[1],
                BOTTOM_LEFT: pontos[2],
                BOTTOM_RIGHT: pontos[3]
            };
        }

        if (typeof pontos === "object") {
            const normalizado = {};

            ORDEM_CANTOS.forEach((chave) => {
                const ponto = pontos[chave];

                if (ponto && Number.isFinite(Number(ponto.x)) && Number.isFinite(Number(ponto.y))) {
                    normalizado[chave] = {
                        x: Number(ponto.x),
                        y: Number(ponto.y)
                    };
                }
            });

            return normalizado;
        }

        return {};
    }

    function clonarCantos(pontos) {
        return JSON.parse(JSON.stringify(pontos || {}));
    }

    function obterCantosDaLeitura(nome) {
        const leitura = leituras[nome] || {};
        return normalizarCantosLidos(leitura.pontos_cantos);
    }

    function gerarCantosPadrao() {
        if (!imagemPrincipal.naturalWidth || !imagemPrincipal.naturalHeight) {
            return {};
        }

        const margemX = Math.max(imagemPrincipal.naturalWidth * 0.035, 28);
        const margemY = Math.max(imagemPrincipal.naturalHeight * 0.035, 28);

        return {
            TOP_LEFT: {
                x: margemX,
                y: margemY
            },
            TOP_RIGHT: {
                x: imagemPrincipal.naturalWidth - margemX,
                y: margemY
            },
            BOTTOM_LEFT: {
                x: margemX,
                y: imagemPrincipal.naturalHeight - margemY
            },
            BOTTOM_RIGHT: {
                x: imagemPrincipal.naturalWidth - margemX,
                y: imagemPrincipal.naturalHeight - margemY
            }
        };
    }

    function garantirCantosVisiveis(nome) {
        if (!nome) {
            return;
        }

        garantirEstadoDaImagem(nome);

        if (Object.keys(cantosEdicao[nome] || {}).length === 4) {
            return;
        }

        cantosEdicao[nome] = clonarCantos(gerarCantosPadrao());
    }

    function garantirEstadoDaImagem(nome) {
        if (!correcoes[nome]) {
            correcoes[nome] = [];
        }

        if (!cantosEdicao[nome]) {
            cantosEdicao[nome] = clonarCantos(obterCantosDaLeitura(nome));
        }
    }

    function atualizarAjuda() {
        if (!viewerHelp) return;

        if (modoEdicao === "cantos") {
            viewerHelp.textContent = `Clique na imagem para posicionar o ${ROTULOS_CANTOS[cantoSelecionado]}. Botão direito remove o canto selecionado.`;
            return;
        }

        viewerHelp.textContent = "Botão esquerdo adiciona marcação | Botão direito remove a marcação mais próxima";
    }

    function atualizarBotoesCanto() {
        const pontos = cantosEdicao[imagemAtual] || {};
        const emModoCantos = modoEdicao === "cantos";

        botoesCanto.forEach((botao) => {
            const chave = botao.dataset.corner;
            botao.classList.toggle("ativo", emModoCantos && chave === cantoSelecionado);
            botao.classList.toggle("definido", Boolean(pontos[chave]));
        });

        markerToolbarGroup?.classList.toggle("oculto", emModoCantos);
        cornerPillsGroup?.classList.toggle("oculto", !emModoCantos);
        btnReprocessarImagem?.classList.toggle("oculto", !emModoCantos);

        if (modoEdicaoSelect) {
            modoEdicaoSelect.value = modoEdicao;
        }
    }

    function renderizarOverlay() {
        overlay.innerHTML = "";

        if (!imagemAtual || !imagemPrincipal.naturalWidth) {
            return;
        }

        if (modoEdicao === "marcacoes") {
            desenharMarcacoes();
            return;
        }

        desenharCantos();
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
        renderizarOverlay();
    }

    function ajustarOverlay() {
        if (!imagemPrincipal || !overlay || !imageWrapper) return;

        overlay.style.width = `${imagemPrincipal.clientWidth}px`;
        overlay.style.height = `${imagemPrincipal.clientHeight}px`;
        overlay.style.left = "0px";
        overlay.style.top = "0px";
    }

    function selecionarImagem(nome, bustCache = false) {
        if (!nome) {
            return;
        }

        imagemAtual = nome;
        garantirEstadoDaImagem(nome);
        nomeImagem.textContent = nome;
        atualizarAjuda();
        atualizarBotoesCanto();

        let urlImagem = `/imagem/${NOME_PROCESSAMENTO}/${encodeURIComponent(nome)}`;

        if (bustCache) {
            urlImagem += `?v=${Date.now()}`;
        }

        imagemPrincipal.src = urlImagem;

        imagemPrincipal.onload = () => {
            garantirCantosVisiveis(nome);
            zoom = zoomSelect.value || "fit-width";
            atualizarBotoesCanto();
            aplicarZoom();
        };

        imagemPrincipal.onerror = () => {
            mostrarToast(
                "Erro ao carregar a imagem. Confira se ela existe na pasta debug_omr.",
                "error",
                "Falha ao abrir imagem"
            );
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

    function desenharCantos() {
        const pontos = cantosEdicao[imagemAtual] || {};
        const rect = imagemPrincipal.getBoundingClientRect();
        const escalaX = rect.width / imagemPrincipal.naturalWidth;
        const escalaY = rect.height / imagemPrincipal.naturalHeight;

        if (ORDEM_CANTOS.every((chave) => Boolean(pontos[chave]))) {
            const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
            svg.setAttribute("viewBox", `0 0 ${rect.width} ${rect.height}`);
            svg.setAttribute("class", "corner-guide");

            const polyline = document.createElementNS("http://www.w3.org/2000/svg", "polyline");
            polyline.setAttribute(
                "points",
                [
                    `${pontos.TOP_LEFT.x * escalaX},${pontos.TOP_LEFT.y * escalaY}`,
                    `${pontos.TOP_RIGHT.x * escalaX},${pontos.TOP_RIGHT.y * escalaY}`,
                    `${pontos.BOTTOM_RIGHT.x * escalaX},${pontos.BOTTOM_RIGHT.y * escalaY}`,
                    `${pontos.BOTTOM_LEFT.x * escalaX},${pontos.BOTTOM_LEFT.y * escalaY}`,
                    `${pontos.TOP_LEFT.x * escalaX},${pontos.TOP_LEFT.y * escalaY}`
                ].join(" ")
            );
            svg.appendChild(polyline);
            overlay.appendChild(svg);
        }

        ORDEM_CANTOS.forEach((chave) => {
            const pontoAtual = pontos[chave];

            if (!pontoAtual) {
                return;
            }

            const handle = document.createElement("div");
            handle.className = "corner-handle";
            handle.style.left = `${pontoAtual.x * escalaX}px`;
            handle.style.top = `${pontoAtual.y * escalaY}px`;
            overlay.appendChild(handle);

            const label = document.createElement("div");
            label.className = "corner-label";
            label.textContent = ABREVIACOES_CANTOS[chave];
            label.style.left = `${pontoAtual.x * escalaX}px`;
            label.style.top = `${pontoAtual.y * escalaY}px`;
            overlay.appendChild(label);
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

        renderizarOverlay();
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
            renderizarOverlay();
        }
    }

    function proximoCanto(chave) {
        const indice = ORDEM_CANTOS.indexOf(chave);
        return ORDEM_CANTOS[(indice + 1) % ORDEM_CANTOS.length];
    }

    function definirCantoAtual(event) {
        if (!imagemAtual) return;

        const coord = coordenadaNaImagem(event);
        garantirEstadoDaImagem(imagemAtual);
        cantosEdicao[imagemAtual][cantoSelecionado] = {
            x: coord.x,
            y: coord.y
        };
        cantoSelecionado = proximoCanto(cantoSelecionado);
        atualizarAjuda();
        atualizarBotoesCanto();
        renderizarOverlay();
    }

    function removerCantoSelecionado() {
        if (!imagemAtual || !cantosEdicao[imagemAtual]) return;

        delete cantosEdicao[imagemAtual][cantoSelecionado];
        atualizarBotoesCanto();
        renderizarOverlay();
    }

    async function salvarMarcacoes() {
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
            mostrarToast("Marcações salvas com sucesso.", "success", "Marcações salvas");
        } else {
            mostrarToast("Erro ao salvar marcações.", "error", "Falha ao salvar");
        }
    }

    async function reprocessarImagemAtual() {
        if (!imagemAtual) {
            mostrarToast("Selecione uma imagem antes de reprocessar.", "warning", "Imagem necessária");
            return;
        }

        const pontos = cantosEdicao[imagemAtual] || {};
        const faltantes = ORDEM_CANTOS.filter((chave) => !pontos[chave]);

        if (faltantes.length) {
            mostrarToast("Defina os 4 cantos antes de reprocessar a imagem.", "warning", "Cantos incompletos");
            return;
        }

        btnReprocessarImagem.disabled = true;
        btnReprocessarImagem.textContent = "⟳";

        try {
            const resposta = await fetch(`/reprocessar-imagem/${NOME_PROCESSAMENTO}`, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({
                    nome_imagem: imagemAtual,
                    pontos_cantos: pontos
                })
            });

            const payload = await resposta.json();

            if (!resposta.ok || payload.status !== "ok") {
                throw new Error(payload.mensagem || "Falha ao reprocessar a imagem.");
            }

            await carregarLeituras();
            cantosEdicao[imagemAtual] = clonarCantos(obterCantosDaLeitura(imagemAtual));
            selecionarImagem(imagemAtual, true);
            mostrarToast("Imagem reprocessada com sucesso.", "success", "Leitura atualizada");
        } catch (erro) {
            mostrarToast(erro.message || "Erro ao reprocessar a imagem.", "error", "Falha no reprocessamento");
        } finally {
            btnReprocessarImagem.disabled = false;
            btnReprocessarImagem.textContent = "↻";
        }
    }

    document.querySelectorAll(".item-imagem").forEach((botao) => {
        botao.addEventListener("click", () => {
            document.querySelectorAll(".item-imagem").forEach((item) => {
                item.classList.remove("ativo");
            });
            botao.classList.add("ativo");
            selecionarImagem(botao.dataset.imagem);
        });
    });

    botoesCanto.forEach((botao) => {
        botao.addEventListener("click", () => {
            modoEdicao = "cantos";
            if (modoEdicaoSelect) {
                modoEdicaoSelect.value = "cantos";
            }
            cantoSelecionado = botao.dataset.corner;
            garantirCantosVisiveis(imagemAtual);
            atualizarAjuda();
            atualizarBotoesCanto();
            renderizarOverlay();
        });
    });

    modoEdicaoSelect?.addEventListener("change", () => {
        modoEdicao = modoEdicaoSelect.value || "marcacoes";
        if (modoEdicao === "cantos") {
            garantirCantosVisiveis(imagemAtual);
        }
        atualizarAjuda();
        atualizarBotoesCanto();
        renderizarOverlay();
    });

    overlay?.addEventListener("click", (event) => {
        event.preventDefault();
        event.stopPropagation();

        if (modoEdicao === "cantos") {
            definirCantoAtual(event);
            return;
        }

        adicionarMarcacao(event);
    });

    overlay?.addEventListener("contextmenu", (event) => {
        event.preventDefault();
        event.stopPropagation();

        if (modoEdicao === "cantos") {
            removerCantoSelecionado();
            return false;
        }

        removerMarcacao(event);
        return false;
    });

    imageWrapper?.addEventListener("contextmenu", (event) => {
        event.preventDefault();
        event.stopPropagation();

        if (modoEdicao === "cantos") {
            removerCantoSelecionado();
            return false;
        }

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
        zoom = valor === "fit-width" || valor === "fit-window" ? valor : Number(valor);
        aplicarZoom();
    });

    document.getElementById("btn-salvar")?.addEventListener("click", salvarMarcacoes);
    btnReprocessarImagem?.addEventListener("click", reprocessarImagemAtual);

    window.addEventListener("resize", () => {
        ajustarOverlay();
        renderizarOverlay();
    });

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

        selecionarImagemPorIndice(botoes.indexOf(atual) + 1);
    }

    function irParaImagemAnterior() {
        const botoes = Array.from(document.querySelectorAll(".item-imagem"));
        const atual = imagemSelecionadaAtual();

        if (!botoes.length) return;

        selecionarImagemPorIndice(botoes.indexOf(atual) - 1);
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

    Promise.all([carregarCorrecoes(), carregarLeituras()]).then(() => {
        atualizarAjuda();
        atualizarBotoesCanto();

        const primeiroBotao = document.querySelector(".item-imagem");

        if (primeiroBotao) {
            primeiroBotao.click();
        }
    });
});
