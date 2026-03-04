<div align="center">
  <img src="assets/opengym-banner.svg" alt="OpenGym banner" width="100%" />

  # OpenGym
  **Open template-репозиторий для LLM-проектов**

  [![Status](https://img.shields.io/badge/status-template-22c55e)](#)
  [![Contributions](https://img.shields.io/badge/contributions-welcome-3b82f6)](CONTRIBUTING.md)
  [![License](https://img.shields.io/badge/license-MIT-black)](LICENSE)
</div>

---

## 📌 Что это

`OpenGym` — базовый шаблон репозитория под проекты, где основная логика, эксперименты и процессы завязаны на LLM.

В этом шаблоне уже есть:
- понятная структура `docs/` и `prompts/`;
- правила для контрибьюторов;
- заготовки системных и рабочих промптов;
- дорожная карта и changelog;
- минимальный CI-чек для markdown-файлов.

---

## 🚀 Быстрый старт

```bash
# 1) Клонируйте репозиторий
 git clone <your-repo-url>
 cd OpenGym

# 2) Создайте первую ветку
 git checkout -b chore/bootstrap-llm-template

# 3) Заполните ключевые места:
# - README.md (описание вашего проекта)
# - docs/LLM_GUIDE.md (правила работы с моделями)
# - prompts/system.md (базовый system prompt)
```

---

## 🧱 Рекомендуемая структура

```text
OpenGym/
├─ assets/                # Логотипы, баннеры, изображения
├─ docs/
│  ├─ LLM_GUIDE.md        # Главный гайд по использованию LLM в проекте
│  └─ ROADMAP.md          # Планы и этапы развития
├─ prompts/
│  ├─ system.md           # Базовый системный промпт
│  └─ task-template.md    # Шаблон промпта под конкретные задачи
├─ .github/workflows/
│  └─ docs-check.yml      # Простейшая CI-проверка
├─ CHANGELOG.md
├─ CONTRIBUTING.md
├─ LICENSE
└─ README.md
```

---

## 🧠 Как использовать как LLM-шаблон

1. **Опишите контекст проекта** в `README.md` и `docs/LLM_GUIDE.md`.
2. **Зафиксируйте базовое поведение модели** в `prompts/system.md`.
3. **Соберите повторно используемые сценарии** в `prompts/task-template.md`.
4. **Ведите изменения итеративно** через `CHANGELOG.md`.
5. **Держите roadmap в актуальном состоянии** в `docs/ROADMAP.md`.

---

## ✅ Next steps

- [ ] Добавить доменные датасеты/ссылки в `docs/LLM_GUIDE.md`
- [ ] Добавить evaluation-кейсы (golden tests)
- [ ] Подключить реальные quality gates в CI
- [ ] Описать production-пайплайн (если нужен)

---

## 🤝 Контрибьютинг

Смотри [CONTRIBUTING.md](CONTRIBUTING.md).

## 📜 Лицензия

MIT — см. [LICENSE](LICENSE).
