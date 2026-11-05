# Сессия Instagram для highlights

Highlights в Instagram недоступны без авторизованной сессии, поэтому iqsaved
их не отдаёт. Для этой функции используется Instaloader.

1. Установите Instaloader локально (или используйте backend venv):

   ```bash
   cd backend
   uv run instaloader --login=ВАШ_АККАУНТ --sessionfile=instagram-session
   ```

2. Положите файл `instagram-session` в эту папку:

   ```bash
   mv instagram-session secrets/instagram-session
   ```

3. В `.env` укажите:

   ```env
   INS_INSTAGRAM_LOGIN=ВАШ_АККАУНТ
   INS_INSTAGRAM_SESSION_FILE=/secrets/instagram-session
   ```

4. Перезапустите контейнеры:

   ```bash
   docker compose up -d --build
   ```

Файл сессии — это секрет. Не коммитьте его в git.
