    def calculate_score(self):
        """Calcula a nota baseada nas respostas com normalização robusta de tipos."""
        import logging
        logger = logging.getLogger(__name__)
        
        # Força refresh do quiz para pegar dados atualizados
        self.quiz.refresh_from_db()
        
        # Busca todas as perguntas do quiz (força nova query)
        questions = list(self.quiz.questions.all().prefetch_related('choices').order_by('order'))
        total = len(questions)
        
        if total == 0:
            self.correct_answers = 0
            self.total_questions = 0
            self.score = 0
            self.is_passed = False
            self.save()
            return 0
        
        # PASSO 1: Normalização de chaves - cria dicionário limpo com todas as chaves como strings
        normalized_answers = {}
        for key, value in self.answers.items():
            # Remove prefixo 'question_' se existir e converte para string
            clean_key = str(key).replace('question_', '')
            # Garante que o valor seja string
            clean_value = str(value).strip()
            if clean_value:  # Só adiciona se não estiver vazio
                normalized_answers[clean_key] = clean_value
        
        logger.info(f'=== CALCULANDO PONTUAÇÃO - QUIZ {self.quiz.id} ===')
        logger.info(f'Respostas originais: {self.answers}')
        logger.info(f'Respostas normalizadas: {normalized_answers}')
        logger.info(f'Total de perguntas: {total}')
        
        # PASSO 2: Cria mapa de escolhas corretas por pergunta (chaves como strings)
        correct_choices_map = {}
        for question in questions:
            question_id_str = str(question.id)
            # Busca todas as escolhas corretas desta pergunta
            correct_choices = list(Choice.objects.filter(question=question, is_correct=True))
            if correct_choices:
                correct_choices_map[question_id_str] = [c.id for c in correct_choices]
            else:
                # VALIDAÇÃO DE INTEGRIDADE: Se não tem escolha correta, loga erro
                logger.error(f'⚠️ Pergunta {question.id} não tem nenhuma opção marcada como correta!')
                correct_choices_map[question_id_str] = []
        
        logger.info(f'Mapa de escolhas corretas: {correct_choices_map}')
        
        # PASSO 3: Processa cada pergunta com comparação robusta
        correct = 0
        for question in questions:
            question_id_str = str(question.id)
            logger.info(f'\n--- Processando Pergunta {question.id} ({question.text[:50]}) ---')
            
            # Busca a resposta normalizada (chave sempre string)
            selected_choice_id_str = normalized_answers.get(question_id_str)
            
            if not selected_choice_id_str:
                # FALLBACK DE SEGURANÇA: Sem resposta = incorreta
                logger.warning(f'Pergunta {question.id} sem resposta - contada como incorreta')
                continue
            
            # PASSO 4: Comparação de tipos - converte para int para comparar
            try:
                selected_choice_id = int(selected_choice_id_str)
            except (ValueError, TypeError) as e:
                logger.error(f'Erro ao converter selected_choice_id "{selected_choice_id_str}" para int: {e}')
                continue
            
            # PASSO 5: Verifica se a escolha selecionada está na lista de corretas
            correct_choice_ids = correct_choices_map.get(question_id_str, [])
            
            if selected_choice_id in correct_choice_ids:
                correct += 1
                logger.info(f'✓ RESPOSTA CORRETA! Escolha {selected_choice_id} está na lista de corretas {correct_choice_ids}')
            else:
                # Verifica diretamente no banco como fallback (caso o mapa não tenha sido populado corretamente)
                try:
                    selected_choice = Choice.objects.get(id=selected_choice_id, question=question)
                    if selected_choice.is_correct:
                        correct += 1
                        logger.info(f'✓ RESPOSTA CORRETA (fallback)! Escolha {selected_choice_id} é correta')
                    else:
                        logger.info(f'✗ Resposta incorreta. Escolha {selected_choice_id} não está na lista de corretas')
                except Choice.DoesNotExist:
                    logger.error(f'✗ Escolha ID {selected_choice_id} não existe para pergunta {question.id}')
        
        logger.info(f'\n=== RESULTADO FINAL ===')
        logger.info(f'Corretas: {correct}/{total}')
        
        # Salva resultados
        self.correct_answers = correct
        self.total_questions = total
        self.score = round((correct / total) * 100) if total > 0 else 0
        self.is_passed = self.score >= self.quiz.passing_score
        self.save()
        
        return self.score
