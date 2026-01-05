/**
 * Multi-Select Dropdown com Checkboxes
 * Componente customizado para seleção múltipla de usuários
 */
class MultiSelectDropdown {
    constructor(element) {
        this.container = element;
        this.trigger = element.querySelector('.multi-select-dropdown__trigger');
        this.dropdown = element.querySelector('.multi-select-dropdown__dropdown');
        this.searchInput = element.querySelector('.multi-select-dropdown__search-input');
        this.selectAll = element.querySelector('.multi-select-dropdown__select-all');
        this.selectAllCheckbox = element.querySelector('.multi-select-dropdown__select-all-checkbox');
        this.options = Array.from(element.querySelectorAll('.multi-select-dropdown__option'));
        this.hiddenInput = element.querySelector('input[type="hidden"]');
        this.triggerText = element.querySelector('.multi-select-dropdown__trigger-text');
        this.triggerIcon = element.querySelector('.multi-select-dropdown__trigger-icon');
        this.placeholder = this.triggerText.dataset.placeholder || 'Selecione os colaboradores';
        
        this.isOpen = false;
        this.selectedValues = new Set();
        this.allValues = new Set();
        
        // Inicializar valores selecionados do input hidden
        if (this.hiddenInput && this.hiddenInput.value) {
            try {
                const values = JSON.parse(this.hiddenInput.value);
                values.forEach(val => this.selectedValues.add(String(val)));
            } catch (e) {
                // Se não for JSON, tentar como string separada por vírgulas
                const values = this.hiddenInput.value.split(',').filter(v => v.trim());
                values.forEach(val => this.selectedValues.add(val.trim()));
            }
        }
        
        // Coletar todos os valores disponíveis
        this.options.forEach(option => {
            const checkbox = option.querySelector('.multi-select-dropdown__option-checkbox');
            const value = checkbox.value;
            this.allValues.add(value);
            
            if (this.selectedValues.has(value)) {
                checkbox.checked = true;
            }
        });
        
        this.init();
    }
    
    init() {
        // Event listeners
        this.trigger.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            this.toggle();
        });
        
        // Fechar ao clicar fora
        document.addEventListener('click', (e) => {
            if (!this.container.contains(e.target)) {
                this.close();
            }
        });
        
        // Search
        if (this.searchInput) {
            this.searchInput.addEventListener('input', (e) => {
                this.filterOptions(e.target.value);
            });
        }
        
        // Select all
        if (this.selectAll) {
            this.selectAll.addEventListener('click', () => {
                this.toggleSelectAll();
            });
            
            if (this.selectAllCheckbox) {
                this.selectAllCheckbox.addEventListener('click', (e) => {
                    e.stopPropagation();
                    this.toggleSelectAll();
                });
            }
        }
        
        // Options
        this.options.forEach(option => {
            const checkbox = option.querySelector('.multi-select-dropdown__option-checkbox');
            const label = option.querySelector('.multi-select-dropdown__option-label');
            
            option.addEventListener('click', (e) => {
                if (e.target !== checkbox) {
                    e.preventDefault();
                    checkbox.checked = !checkbox.checked;
                }
                this.handleOptionChange(checkbox);
            });
            
            checkbox.addEventListener('change', () => {
                this.handleOptionChange(checkbox);
            });
        });
        
        this.updateTriggerText();
        this.updateSelectAllState();
    }
    
    toggle() {
        if (this.isOpen) {
            this.close();
        } else {
            this.open();
        }
    }
    
    open() {
        this.isOpen = true;
        this.trigger.classList.add('multi-select-dropdown__trigger--open');
        this.dropdown.classList.add('multi-select-dropdown__dropdown--open');
        if (this.triggerIcon) {
            this.triggerIcon.classList.add('multi-select-dropdown__trigger-icon--open');
        }
        
        // Focus no search input se existir
        if (this.searchInput) {
            setTimeout(() => {
                this.searchInput.focus();
            }, 100);
        }
    }
    
    close() {
        this.isOpen = false;
        this.trigger.classList.remove('multi-select-dropdown__trigger--open');
        this.dropdown.classList.remove('multi-select-dropdown__dropdown--open');
        if (this.triggerIcon) {
            this.triggerIcon.classList.remove('multi-select-dropdown__trigger-icon--open');
        }
        
        // Limpar busca
        if (this.searchInput) {
            this.searchInput.value = '';
            this.filterOptions('');
        }
    }
    
    filterOptions(query) {
        const lowerQuery = query.toLowerCase().trim();
        this.options.forEach(option => {
            const label = option.querySelector('.multi-select-dropdown__option-label');
            const text = label.textContent.toLowerCase();
            
            if (text.includes(lowerQuery)) {
                option.classList.remove('multi-select-dropdown__option--hidden');
            } else {
                option.classList.add('multi-select-dropdown__option--hidden');
            }
        });
    }
    
    handleOptionChange(checkbox) {
        const value = checkbox.value;
        
        if (checkbox.checked) {
            this.selectedValues.add(value);
        } else {
            this.selectedValues.delete(value);
        }
        
        this.updateHiddenInput();
        this.updateTriggerText();
        this.updateSelectAllState();
    }
    
    toggleSelectAll() {
        const allVisible = this.getVisibleOptions();
        const allChecked = allVisible.every(opt => {
            const checkbox = opt.querySelector('.multi-select-dropdown__option-checkbox');
            return checkbox.checked;
        });
        
        allVisible.forEach(option => {
            const checkbox = option.querySelector('.multi-select-dropdown__option-checkbox');
            checkbox.checked = !allChecked;
            this.handleOptionChange(checkbox);
        });
    }
    
    getVisibleOptions() {
        return this.options.filter(opt => 
            !opt.classList.contains('multi-select-dropdown__option--hidden')
        );
    }
    
    updateSelectAllState() {
        if (!this.selectAllCheckbox) return;
        
        const visibleOptions = this.getVisibleOptions();
        if (visibleOptions.length === 0) {
            this.selectAllCheckbox.checked = false;
            this.selectAllCheckbox.indeterminate = false;
            return;
        }
        
        const checkedCount = visibleOptions.filter(opt => {
            const checkbox = opt.querySelector('.multi-select-dropdown__option-checkbox');
            return checkbox.checked;
        }).length;
        
        if (checkedCount === 0) {
            this.selectAllCheckbox.checked = false;
            this.selectAllCheckbox.indeterminate = false;
        } else if (checkedCount === visibleOptions.length) {
            this.selectAllCheckbox.checked = true;
            this.selectAllCheckbox.indeterminate = false;
        } else {
            this.selectAllCheckbox.checked = false;
            this.selectAllCheckbox.indeterminate = true;
        }
    }
    
    updateTriggerText() {
        if (this.selectedValues.size === 0) {
            this.triggerText.textContent = this.placeholder;
            this.triggerText.classList.add('multi-select-dropdown__trigger-text--placeholder');
        } else if (this.selectedValues.size === 1) {
            const value = Array.from(this.selectedValues)[0];
            const option = this.options.find(opt => {
                const checkbox = opt.querySelector('.multi-select-dropdown__option-checkbox');
                return checkbox.value === value;
            });
            if (option) {
                const label = option.querySelector('.multi-select-dropdown__option-label');
                this.triggerText.textContent = label.textContent;
                this.triggerText.classList.remove('multi-select-dropdown__trigger-text--placeholder');
            }
        } else {
            this.triggerText.textContent = `${this.selectedValues.size} colaboradores selecionados`;
            this.triggerText.classList.remove('multi-select-dropdown__trigger-text--placeholder');
        }
    }
    
    updateHiddenInput() {
        if (this.hiddenInput) {
            const values = Array.from(this.selectedValues);
            this.hiddenInput.value = JSON.stringify(values);
        }
    }
    
    getSelectedValues() {
        return Array.from(this.selectedValues);
    }
}

// Exportar para uso global
window.MultiSelectDropdown = MultiSelectDropdown;

// Inicializar todos os multi-select dropdowns quando o DOM estiver pronto
document.addEventListener('DOMContentLoaded', () => {
    const dropdowns = document.querySelectorAll('.multi-select-dropdown');
    dropdowns.forEach(dropdown => {
        new MultiSelectDropdown(dropdown);
    });
});
