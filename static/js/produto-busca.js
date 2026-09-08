/*
 * produto-busca.js
 * ---------------------------------------------------------------------
 * Busca dinâmica (autocomplete / live search) de produtos, sem AJAX:
 * lê os dados diretamente das <option> de um <select> já renderizado
 * pelo servidor (com atributos data-sku / data-detalhes / data-qtd /
 * data-unidade — ver ProdutoSelect em estoque/forms.py) e filtra a lista
 * em tempo real conforme o usuário digita.
 *
 * Usado em:
 *   - movimentacao_form.html  (substitui o <select> de produto)
 *   - requisicao_form.html    (seleciona o produto a adicionar à lista)
 * ---------------------------------------------------------------------
 */

function attachProdutoBusca(sourceSelectEl, inputEl, dropdownEl, onSelect) {
    if (!sourceSelectEl || !inputEl || !dropdownEl) {
        return;
    }

    // Monta a lista de produtos a partir das <option> do select-fonte.
    var produtos = [];
    Array.prototype.forEach.call(sourceSelectEl.options, function (opt) {
        if (!opt.value) {
            return; // ignora a opção vazia ("---------")
        }
        produtos.push({
            id: opt.value,
            label: opt.textContent.trim(),
            sku: opt.getAttribute('data-sku') || '',
            detalhes: opt.getAttribute('data-detalhes') || '',
            qtd: opt.getAttribute('data-qtd') || '',
            unidade: opt.getAttribute('data-unidade') || '',
        });
    });

    var indiceAtivo = -1;
    var resultadosAtuais = [];

    function esconderDropdown() {
        dropdownEl.classList.remove('show');
        dropdownEl.innerHTML = '';
        indiceAtivo = -1;
        resultadosAtuais = [];
    }

    function selecionar(produto) {
        if (typeof onSelect === 'function') {
            onSelect(produto);
        }
        esconderDropdown();
    }

    function renderDropdown(lista) {
        dropdownEl.innerHTML = '';
        resultadosAtuais = lista;
        indiceAtivo = -1;

        if (lista.length === 0) {
            var vazio = document.createElement('div');
            vazio.className = 'produto-busca-empty';
            vazio.textContent = 'Nenhum produto encontrado.';
            dropdownEl.appendChild(vazio);
            dropdownEl.classList.add('show');
            return;
        }

        lista.forEach(function (produto, idx) {
            var item = document.createElement('div');
            item.className = 'produto-busca-item';
            item.setAttribute('data-idx', idx);

            var nomeEl = document.createElement('span');
            nomeEl.className = 'produto-busca-item-nome';
            nomeEl.textContent = produto.label;
            item.appendChild(nomeEl);

            var metaEl = document.createElement('span');
            metaEl.className = 'produto-busca-item-meta';
            var partesMeta = [];
            if (produto.sku) { partesMeta.push('Cód: ' + produto.sku); }
            if (produto.detalhes) { partesMeta.push(produto.detalhes); }
            partesMeta.push('Estoque: ' + (produto.qtd || '0') + ' ' + produto.unidade);
            metaEl.textContent = partesMeta.join(' • ');
            item.appendChild(metaEl);

            item.addEventListener('mousedown', function (e) {
                e.preventDefault(); // evita perder o foco do input antes do click
                selecionar(produto);
            });

            dropdownEl.appendChild(item);
        });

        dropdownEl.classList.add('show');
    }

    function filtrar(termoBruto) {
        var termo = termoBruto.trim().toLowerCase();
        if (!termo) {
            esconderDropdown();
            return;
        }
        var filtrados = produtos.filter(function (p) {
            return (
                p.label.toLowerCase().indexOf(termo) !== -1 ||
                p.sku.toLowerCase().indexOf(termo) !== -1 ||
                p.detalhes.toLowerCase().indexOf(termo) !== -1
            );
        }).slice(0, 8);
        renderDropdown(filtrados);
    }

    function marcarAtivo(novoIndice) {
        var itens = dropdownEl.querySelectorAll('.produto-busca-item');
        itens.forEach(function (el) { el.classList.remove('active'); });
        if (novoIndice >= 0 && novoIndice < itens.length) {
            itens[novoIndice].classList.add('active');
            itens[novoIndice].scrollIntoView({ block: 'nearest' });
        }
        indiceAtivo = novoIndice;
    }

    // Enquanto o usuário digita, filtra e exibe instantaneamente (live search).
    inputEl.addEventListener('input', function () {
        filtrar(inputEl.value);
    });

    inputEl.addEventListener('focus', function () {
        if (inputEl.value.trim()) {
            filtrar(inputEl.value);
        }
    });

    // Navegação por teclado: setas para percorrer, Enter para selecionar, Esc para fechar.
    inputEl.addEventListener('keydown', function (e) {
        if (!dropdownEl.classList.contains('show')) {
            return;
        }
        if (e.key === 'ArrowDown') {
            e.preventDefault();
            marcarAtivo(Math.min(indiceAtivo + 1, resultadosAtuais.length - 1));
        } else if (e.key === 'ArrowUp') {
            e.preventDefault();
            marcarAtivo(Math.max(indiceAtivo - 1, 0));
        } else if (e.key === 'Enter') {
            if (indiceAtivo >= 0 && resultadosAtuais[indiceAtivo]) {
                e.preventDefault();
                selecionar(resultadosAtuais[indiceAtivo]);
            }
        } else if (e.key === 'Escape') {
            esconderDropdown();
        }
    });

    // Fecha o dropdown ao clicar fora do campo de busca.
    document.addEventListener('click', function (e) {
        if (e.target !== inputEl && !dropdownEl.contains(e.target)) {
            esconderDropdown();
        }
    });
}
