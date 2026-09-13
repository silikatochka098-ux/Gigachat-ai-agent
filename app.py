import streamlit as st

from drawing_analyzer import (
    analyze_drawing,
    update_parameters_from_user_answer,
    check_required_parameters,
    make_clarification_question,
)

from calculator import calculate_from_ai_parameters


# ============================================================
# НАСТРОЙКА СТРАНИЦЫ
# ============================================================

st.set_page_config(
    page_title="AI-помощник по расчёту изделий",
    page_icon="🤖",
    layout="wide",
)


# ============================================================
# ЗАГОЛОВОК
# ============================================================

st.title("🤖 AI-помощник по расчёту стоимости изделия")

st.write(
    "Загрузите чертёж изделия и при необходимости добавьте "
    "текстовое описание. ИИ извлечёт параметры, уточнит "
    "недостающие данные и передаст их в Excel-калькулятор. "
    "Поддерживаются PDF, изображения, DXF, CDW и M3D."
)


# ============================================================
# СОСТОЯНИЕ ПРИЛОЖЕНИЯ
# ============================================================

if "parameters" not in st.session_state:
    st.session_state.parameters = None

if "current_question" not in st.session_state:
    st.session_state.current_question = None

if "missing_parameters" not in st.session_state:
    st.session_state.missing_parameters = []

if "analysis_done" not in st.session_state:
    st.session_state.analysis_done = False

if "uploaded_file" not in st.session_state:
    st.session_state.uploaded_file = None

if "calculation_done" not in st.session_state:
    st.session_state.calculation_done = False

if "calculation_error" not in st.session_state:
    st.session_state.calculation_error = None

if "output_path" not in st.session_state:
    st.session_state.output_path = None


# ============================================================
# ЗАГРУЗКА ФАЙЛА
# ============================================================

uploaded_file = st.file_uploader(
    "📎 Загрузите чертёж",
    type=[
        "pdf",
        "png",
        "jpg",
        "jpeg",
        "webp",
        "dxf",
        "cdw",
        "m3d",
        "dks",
    ],
)


# ============================================================
# ОПИСАНИЕ ИЗДЕЛИЯ
# ============================================================

description = st.text_area(
    "📝 Дополнительное описание изделия",
    placeholder=(
        "Например: верхняя панель корпуса, "
        "из листовой стали, требуется гибка..."
    ),
)


# ============================================================
# КНОПКА АНАЛИЗА
# ============================================================

if st.button(
    "🔍 Проанализировать чертёж",
    type="primary",
):

    if uploaded_file is None:
        st.warning("Сначала загрузите чертёж.")

    else:

        with st.spinner(
            "🤖 Анализирую чертёж и извлекаю параметры..."
        ):

            try:

                parameters = analyze_drawing(
                    uploaded_file,
                    description,
                )

                # Сохраняем результат анализа
                st.session_state.parameters = parameters

                st.session_state.analysis_done = True

                st.session_state.uploaded_file = uploaded_file

                st.session_state.current_question = None

                st.session_state.missing_parameters = []

                # Сбрасываем предыдущий расчёт
                st.session_state.calculation_done = False

                st.session_state.calculation_error = None

                st.session_state.output_path = None

                st.success(
                    "✅ Чертёж успешно проанализирован."
                )

            except Exception as e:

                st.error(
                    "❌ Ошибка при анализе чертежа."
                )

                st.exception(e)


# ============================================================
# РЕЗУЛЬТАТ АНАЛИЗА
# ============================================================

if st.session_state.get("analysis_done"):

    st.divider()

    st.subheader("📋 Параметры изделия")

    st.json(
        st.session_state.parameters
    )


    # ========================================================
    # ПРОВЕРЯЕМ НЕДОСТАЮЩИЕ ПАРАМЕТРЫ
    # ========================================================

    missing = check_required_parameters(
        st.session_state.parameters
    )

    st.session_state.missing_parameters = missing


    # ========================================================
    # ЕСЛИ ЕСТЬ НЕДОСТАЮЩИЕ ПАРАМЕТРЫ
    # ========================================================

    if missing:

        st.warning(
            "⚠️ Для продолжения необходимо уточнить "
            "некоторые параметры."
        )


        # ----------------------------------------------------
        # Создаём вопрос
        # ----------------------------------------------------

        if st.session_state.current_question is None:

            st.session_state.current_question = (
                make_clarification_question(
                    missing
                )
            )


        # ----------------------------------------------------
        # Показываем вопрос
        # ----------------------------------------------------

        st.info(
            f"🤖 {st.session_state.current_question}"
        )


        # ----------------------------------------------------
        # Поле ответа
        # ----------------------------------------------------

        user_answer = st.text_input(
            "Ваш ответ:",
            key="user_answer",
        )


        # ----------------------------------------------------
        # Кнопка ответа
        # ----------------------------------------------------

        if st.button(
            "💬 Ответить"
        ):

            if not user_answer.strip():

                st.warning(
                    "Введите ответ."
                )

            else:

                with st.spinner(
                    "🤖 Анализирую ваш ответ..."
                ):

                    try:

                        result = (
                            update_parameters_from_user_answer(
                                st.session_state.parameters,
                                st.session_state.current_question,
                                user_answer,
                            )
                        )

                    except Exception as e:

                        st.error(
                            "❌ Ошибка при обработке ответа."
                        )

                        st.exception(e)

                        result = None


                # ------------------------------------------------
                # Обрабатываем ответ ИИ
                # ------------------------------------------------

                if result:

                    clarification = result.get(
                        "уточнение"
                    )


                    # ============================================
                    # ИИ ЗАДАЛ ЕЩЁ ОДИН ВОПРОС
                    # ============================================

                    if clarification:

                        st.session_state.current_question = (
                            clarification
                        )

                        st.warning(
                            f"🤖 {clarification}"
                        )


                    # ============================================
                    # ИИ ПОЛУЧИЛ НОВЫЕ ПАРАМЕТРЫ
                    # ============================================

                    else:

                        updates = result.get(
                            "обновления",
                            {}
                        )


                        # ----------------------------------------
                        # Записываем обновления в JSON
                        # ----------------------------------------

                        for key, value in updates.items():

                            st.session_state.parameters[
                                key
                            ] = value


                        st.success(
                            "✅ Ответ принят. "
                            "Параметры обновлены."
                        )


                        # ----------------------------------------
                        # Сбрасываем текущий вопрос
                        # ----------------------------------------

                        st.session_state.current_question = None


                        # ----------------------------------------
                        # Перерисовываем страницу
                        # ----------------------------------------

                        st.rerun()


    # ========================================================
    # ВСЕ ПАРАМЕТРЫ ПОЛУЧЕНЫ
    # ========================================================

    else:

        st.success(
            "✅ Все необходимые параметры получены!"
        )

        st.write(
            "ИИ сформировал полный набор параметров. "
            "Теперь их можно передать в Excel-калькулятор."
        )


        # ====================================================
        # ПОКАЗЫВАЕМ ФИНАЛЬНЫЙ JSON
        # ====================================================

        st.subheader(
            "📋 Итоговые параметры"
        )

        st.json(
            st.session_state.parameters
        )


        # ====================================================
        # РАСЧЁТ
        # ====================================================

        st.divider()

        st.subheader(
            "🧮 Расчёт стоимости"
        )

        st.write(
            "Параметры из JSON будут переданы "
            "в существующий Excel-калькулятор."
        )


        if st.button(
            "🧮 Рассчитать стоимость",
            type="primary",
        ):

            # Сбрасываем предыдущий результат
            st.session_state.calculation_done = False

            st.session_state.calculation_error = None

            st.session_state.output_path = None


            with st.spinner(
                "🧮 Передаю параметры в Excel-калькулятор..."
            ):

                try:

                    # ==========================================
                    # JSON ИЗ ИИ
                    # ==========================================

                    parameters = (
                        st.session_state.parameters
                    )


                    # ==========================================
                    # ПЕРЕДАЁМ JSON В КАЛЬКУЛЯТОР
                    # ==========================================

                    output_path = (
                        calculate_from_ai_parameters(
                            parameters=parameters,

                            template_path=(
                                "excel/calculator_template.xlsx"
                            ),

                            output_path=(
                                "КП_готовое.xlsx"
                            ),
                        )
                    )


                    # ==========================================
                    # СОХРАНЯЕМ РЕЗУЛЬТАТ
                    # ==========================================

                    st.session_state.output_path = (
                        output_path
                    )

                    st.session_state.calculation_done = True

                    st.session_state.calculation_error = None


                except Exception as e:

                    st.session_state.calculation_done = False

                    st.session_state.calculation_error = str(e)

                    st.error(
                        "❌ Не удалось выполнить расчёт."
                    )

                    st.exception(e)


        # ====================================================
        # РЕЗУЛЬТАТ РАСЧЁТА
        # ====================================================

        if st.session_state.get(
            "calculation_done"
        ):

            st.success(
                "✅ Расчёт завершён! "
                "Готовое КП сформировано."
            )


            output_path = (
                st.session_state.output_path
            )


            # ================================================
            # КНОПКА СКАЧИВАНИЯ
            # ================================================

            if output_path:

                try:

                    with open(
                        output_path,
                        "rb"
                    ) as file:

                        st.download_button(
                            label="📥 Скачать готовое КП",
                            data=file,
                            file_name="КП_готовое.xlsx",
                            mime=(
                                "application/vnd.openxmlformats-officedocument"
                                ".spreadsheetml.sheet"
                            ),
                        )

                except Exception as e:

                    st.error(
                        "❌ Не удалось открыть готовое КП."
                    )

                    st.exception(e)