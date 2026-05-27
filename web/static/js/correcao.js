
document.addEventListener("DOMContentLoaded", () => {
    let zoom = "fit-width";
    let imagemAtual = null;
    let correcoes = {};
    let leituras = {};
    let cantosEdicao = {};
    let modoEdicao = "marcacoes";
    let cantoSelecionado = "TOP_LEFT";
    let filtroStatus = "todos";

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
    const viewerStatus = document.getElementById("viewer-status");
    const viewerMeta = document.getElementById("viewer-meta");
    const buscaInput = document.getElementById("busca");
    const sidebarTotal = document.getElementById("sidebar-total");
    const sidebarEmpty = document.getElementById("sidebar-empty");
    const countErro = document.getElementById("count-erro");
    const countOk = document.getElementById("count-ok");
    const countManual = document.getElementById("count-manual");
    const btnProximaComErro = document.getElementById("proxima-com-erro");
    const botoesFiltroSidebar = Array.from(document.querySelectorAll(".sidebar-filter-btn"));
    const markerToolbarGroup = document.getElementById("marker-toolbar-group");
    const cornerPillsGroup = document.getElementById("corner-pills-group");
    const toastStack = document.getElementById("toast-stack");
    const botoesCanto = Array.from(document.querySelectorAll(".corner-btn"));
    const STORAGE_KEY = `correcao:${NOME_PROCESSAMENTO}:state`;

    function ajustarOverlay() {
        // O overlay é dimensionado via CSS com 'inset: 0' e seu contêiner '.image-wrapper'
        // tem o tamanho ajustado na função aplicarZoom. Esta função vazia previne erros de referência.
    }

    function obterLeituraAtual(nome = imagemAtual) {
        return leituras[nome] || {};
    }

    function normalizarNomePesquisa(nome) {
        return String(nome || "").replace(/^template_/, "").toLowerCase();
    }

    function foiCorrigidaManualmente(leitura) {
        return String(leitura?.origem_cantos || "").toUpperCase() === "MANUAL";
    }

    function pluralizar(valor, singular, plural) {
        return `${valor} ${valor === 1 ? singular : plural}`;
    }

    function listarErros(leitura) {
        return Array.isArray(leitura?.erros)
            ? leitura.erros.map((erro) => String(erro || "").trim()).filter(Boolean)
            : [];
    }

    function resumirErro(erros) {
        if (!erros.length) {
            return "";
        }

        if (erros.length === 1) {
            return erros[0];
        }

        return erros.slice(0, 2).join(" | ");
    }
    
    function obterResumoImagem(nome) {
        const leitura = obterLeituraAtual(nome);
        const erros = listarErros(leitura);
        const manual = foiCorrigidaManualmente(leitura);

        if (erros.length) {
            const detalheErro = resumirErro(erros);
            return {
                status: "erro",
                rotulo: "Erro",
                meta: detalheErro,
                metaCurta: pluralizar(erros.length, "erro", "erros"),
                manual
            };
        }

        return {
            status: "ok",
            rotulo: "OK",
            meta: manual ? "Leitura revisada com ajuste manual de cantos" : "Leitura sem erros de leitura",
            metaCurta: manual ? "Ajuste manual" : "Sem erro",
            manual
        };
    }

    function selecionarImagem(nomeImagemSelecionada, preservarZoom = false) {

        if (!nomeImagemSelecionada) {
            console.log("sem nome");
            return;
        }

        console.log("selecionando:", nomeImagemSelecionada);

        imagemAtual = nomeImagemSelecionada;

        const nomeLimpo = nomeImagemSelecionada;

        const urlImagem = `/imagem/${NOME_PROCESSAMENTO}/${nomeLimpo}`;

        console.log("URL:", urlImagem);

        imagemPrincipal.onload = () => {

            console.log("imagem carregada");

            ajustarOverlay();

            if (!preservarZoom) {
                zoom = zoomSelect?.value || "fit-width";
            }

            aplicarZoom();
            renderizarOverlay();
            atualizarResumoViewer();
            atualizarBotoesCanto();
            salvarEstadoPainel();
        };

        imagemPrincipal.onerror = () => {
            console.log("erro ao carregar");

            mostrarToast(
                `Erro ao carregar a imagem: ${nomeLimpo}`,
                "error",
                "Falha de leitura"
            );
        };

        imagemPrincipal.src = urlImagem;

        console.log("src definida:", imagemPrincipal.src);

        nomeImagem.textContent = nomeLimpo;
    }

    function salvarEstadoPainel() {
        const estado = {
            busca: buscaInput?.value || "",
            filtroStatus,
            imagemAtual,
            modoEdicao,
            zoomSelect: zoomSelect?.value || "fit-width"
        };

        try {
            window.sessionStorage.setItem(STORAGE_KEY, JSON.stringify(estado));
        } catch (erro) {
            // Ignora falha de storage; a interface continua funcional.
        }
    }

    function carregarEstadoPainel() {
        try {
            const bruto = window.sessionStorage.getItem(STORAGE_KEY);
            return bruto ? JSON.parse(bruto) : {};
        } catch (erro) {
            return {};
        }
    }

    function atualizarResumoViewer() {
        if (!viewerStatus || !viewerMeta || !imagemAtual) {
            return;
        }

        const resumo = obterResumoImagem(imagemAtual);
        viewerStatus.textContent = resumo.rotulo;
        viewerStatus.className = `status-badge viewer-status-badge ${resumo.status}`;
        viewerMeta.textContent = resumo.manual ? `${resumo.meta} | Ajuste manual aplicado` : resumo.meta;
    }

    function atualizarRotuloBotao(botao) {
        const nome = botao.dataset.imagem || "";
        const resumo = obterResumoImagem(nome);
        const nomeCurto = normalizarNomePesquisa(nome);
        const tituloExibicao = String(nome || "").replace(/^template_/, "");
        botao.classList.toggle("com-manual", resumo.manual);
        botao.dataset.status = resumo.status;
        botao.dataset.manual = resumo.manual ? "sim" : "nao";
        botao.dataset.search = `${nomeCurto} ${resumo.rotulo.toLowerCase()} ${resumo.meta.toLowerCase()} ${resumo.metaCurta.toLowerCase()} ${resumo.manual ? "manual corrigida reprocessada" : ""}`;
        botao.innerHTML = `
            <div class="item-imagem-head">
                <div class="item-imagem-title-wrap">
                    <span class="item-imagem-title">${tituloExibicao}</span>
                    <span class="item-imagem-subtitle">${resumo.metaCurta}</span>
                </div>
                <span class="item-imagem-pill ${resumo.status}">${resumo.rotulo}</span>
            </div>
            <div class="item-imagem-meta">
                <span class="item-imagem-detail">${resumo.meta}</span>
                ${resumo.manual ? `<span class="item-imagem-chip manual">Ajuste manual</span>` : ""}
            </div>
        `;
    }

    function decorarListaImagens() {
        document.querySelectorAll(".item-imagem").forEach((botao) => {
            atualizarRotuloBotao(botao);
        });
        atualizarContadoresSidebar();
    }

    function atualizarContadoresSidebar() {
        const botoes = Array.from(document.querySelectorAll(".item-imagem"));
        const total = botoes.length;
        const totalErro = botoes.filter((botao) => botao.dataset.status === "erro").length;
        const totalOk = botoes.filter((botao) => botao.dataset.status === "ok").length;
        const totalManual = botoes.filter((botao) => botao.dataset.manual === "sim").length;

        if (sidebarTotal) sidebarTotal.textContent = pluralizar(total, "imagem", "imagens");
        if (countErro) countErro.textContent = `${totalErro}`;
        if (countOk) countOk.textContent = `${totalOk}`;
        if (countManual) countManual.textContent = `${totalManual}`;
    }

    function atualizarBotoesFiltroSidebar() {
        botoesFiltroSidebar.forEach((botao) => {
            botao.classList.toggle("ativo", botao.dataset.filter === filtroStatus);
        });
    }

    function aplicarFiltroImagens() {
        const termo = (buscaInput?.value || "").trim().toLowerCase();
        const botoes = Array.from(document.querySelectorAll(".item-imagem"));
        let totalVisiveis = 0;

        botoes.forEach((botao) => {
            const texto = botao.dataset.search || normalizarNomePesquisa(botao.dataset.imagem);
            const combinaStatus =
                filtroStatus === "todos"
                || (filtroStatus === "erro" && botao.dataset.status === "erro")
                || (filtroStatus === "manual" && botao.dataset.manual === "sim");
            const visivel = combinaStatus && (!termo || texto.includes(termo));
            botao.classList.toggle("hidden", !visivel);
            if (visivel) {
                totalVisiveis += 1;
            }
        });

        if (imagemAtual) {
            const atual = document.querySelector(`.item-imagem[data-imagem="${CSS.escape(imagemAtual)}"]`);
            if (atual?.classList.contains("hidden")) {
                const primeiroVisivel = document.querySelector(".item-imagem:not(.hidden)");
                if (primeiroVisivel) {
                    primeiroVisivel.click();
                }
            }
        }

        if (sidebarEmpty) {
            sidebarEmpty.hidden = totalVisiveis > 0;
        }

        atualizarBotoesFiltroSidebar();
        salvarEstadoPainel();
    }

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
            viewerHelp.textContent = `Modo cantos: botao esquerdo do MOUSE posiciona o ${ROTULOS_CANTOS[cantoSelecionado]}. Botao direito do MOUSE remove o canto selecionado.`;
            return;
        }

        viewerHelp.textContent = "Vermelho = Errado / nao deve entrar no CSV | Verde = Correto / deve entrar no CSV | Botao esquerdo do MOUSE adiciona marcacao | Botao direito do MOUSE remove a marcacao mais proxima";
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

        salvarEstadoPainel();
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
        const larguraDisponivel = imageArea.clientWidth;
        const alturaDisponivel = imageArea.clientHeight;
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

        // CORREÇÃO: Sincroniza o select visualmente
        if (zoomSelect) {
            // Se for modo automático (fit), mantém o texto correto
            if (zoom === "fit-width" || zoom === "fit-window") {
                zoomSelect.value = zoom;
            } else {
                // Se for manual, tenta achar a opção mais próxima
                const valorFormatado = Number(fatorZoom).toFixed(2);
                const opcaoMaisProxima = Array.from(zoomSelect.options).find(opt => 
                    opt.value !== 'fit-width' && opt.value !== 'fit-window' && 
                    Math.abs(Number(opt.value) - fatorZoom) < 0.05
                );
                if (opcaoMaisProxima) zoomSelect.value = opcaoMaisProxima.value;
            }
        }

        ajustarOverlay();
        renderizarOverlay();
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

        garantirEstadoDaImagem(imagemAtual);

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
            decorarListaImagens();
            aplicarFiltroImagens();
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

    botoesFiltroSidebar.forEach((botao) => {
        botao.addEventListener("click", () => {
            filtroStatus = botao.dataset.filter || "todos";
            aplicarFiltroImagens();
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
        let valorAtual = (typeof zoom === 'number') ? zoom : (imagemPrincipal.clientWidth / imagemPrincipal.naturalWidth);
        zoom = Math.min(valorAtual + 0.15, 3);
        aplicarZoom();
        salvarEstadoPainel();
    });

    document.getElementById("zoom-menos")?.addEventListener("click", () => {
        let valorAtual = (typeof zoom === 'number') ? zoom : (imagemPrincipal.clientWidth / imagemPrincipal.naturalWidth);
        zoom = Math.max(valorAtual - 0.15, 0.12);
        aplicarZoom();
        salvarEstadoPainel();
    });

    zoomSelect?.addEventListener("change", () => {
        const valor = zoomSelect.value;
        zoom = valor === "fit-width" || valor === "fit-window" ? valor : Number(valor);
        aplicarZoom();
        salvarEstadoPainel();
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

    function botoesVisiveis() {
        return Array.from(document.querySelectorAll(".item-imagem")).filter((botao) => !botao.classList.contains("hidden"));
    }

    function selecionarImagemPorIndice(indice) {
        const botoes = botoesVisiveis();

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
        const botoes = botoesVisiveis();
        const atual = imagemSelecionadaAtual();

        if (!botoes.length) return;

        selecionarImagemPorIndice(botoes.indexOf(atual) + 1);
    }

    function irParaImagemAnterior() {
        const botoes = botoesVisiveis();
        const atual = imagemSelecionadaAtual();

        if (!botoes.length) return;

        selecionarImagemPorIndice(botoes.indexOf(atual) - 1);
    }

    function irParaProximaCorrespondencia(predicado, tituloSemResultado) {
        const botoes = botoesVisiveis();
        const atual = imagemSelecionadaAtual();

        if (!botoes.length) return;

        const indiceAtual = Math.max(0, botoes.indexOf(atual));

        for (let deslocamento = 1; deslocamento <= botoes.length; deslocamento += 1) {
            const candidato = botoes[(indiceAtual + deslocamento) % botoes.length];
            if (predicado(candidato)) {
                candidato.click();
                candidato.scrollIntoView({ behavior: "smooth", block: "nearest" });
                return;
            }
        }

        mostrarToast(tituloSemResultado, "warning", "Sem correspondência");
    }

    btnProximaImagem?.addEventListener("click", irParaProximaImagem);
    btnImagemAnterior?.addEventListener("click", irParaImagemAnterior);
    btnProximaComErro?.addEventListener("click", () => {
        irParaProximaCorrespondencia(
            (botao) => botao.dataset.status === "erro",
            "Nenhuma outra imagem com erro foi encontrada no filtro atual."
        );
    });
    buscaInput?.addEventListener("input", aplicarFiltroImagens);

    document.addEventListener("keydown", (event) => {
        if (event.key === "ArrowRight") {
            irParaProximaImagem();
        }

        if (event.key === "ArrowLeft") {
            irParaImagemAnterior();
        }
    });

    Promise.all([carregarCorrecoes(), carregarLeituras()]).then(() => {
        const estado = carregarEstadoPainel();
        if (buscaInput && typeof estado.busca === "string") {
            buscaInput.value = estado.busca;
        }
        if (estado.filtroStatus) {
            filtroStatus = ["todos", "erro", "manual"].includes(estado.filtroStatus)
                ? estado.filtroStatus
                : "todos";
        }
        if (modoEdicaoSelect && estado.modoEdicao) {
            modoEdicao = estado.modoEdicao;
            modoEdicaoSelect.value = estado.modoEdicao;
        }
        if (zoomSelect && estado.zoomSelect) {
            zoomSelect.value = estado.zoomSelect;
        }
        decorarListaImagens();
        atualizarAjuda();
        atualizarBotoesCanto();
        aplicarFiltroImagens();

        const params = new URLSearchParams(window.location.search);
        const imagemSolicitada = params.get("imagem");
        if (imagemSolicitada) {
            filtroStatus = "todos";
        }
        const imagemRestaurada = estado.imagemAtual;
        let primeiroBotao = imagemSolicitada
            ? document.querySelector(`.item-imagem[data-imagem="${CSS.escape(imagemSolicitada)}"]`)
            : imagemRestaurada
                ? document.querySelector(`.item-imagem[data-imagem="${CSS.escape(imagemRestaurada)}"]`)
                : document.querySelector(".item-imagem:not(.hidden)");

        if (primeiroBotao?.classList.contains("hidden")) {
            primeiroBotao = document.querySelector(".item-imagem:not(.hidden)");
        }

        if (primeiroBotao) {
            primeiroBotao.click();
        }
    });
});
