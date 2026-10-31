Автономная лаборатория Git: установленный Git 2.28+ и Python 3.8+.
Нужна вся эта папка, включая template/. Сеть и Docker не используются.
Полный маршрут семи опытов находится в соответствующей главе книги Git.

Запуск из этой папки, с отдельно выбранным каталогом:
  python3 trainer.py --workspace <каталог-стенда> init
  python3 trainer.py --workspace <каталог-стенда> status
  python3 trainer.py --workspace <каталог-стенда> check index
Угловые скобки — место подстановки; не вводите их буквально.

Проверки по ходу маршрута:
  index, branch, merge, recovery, fetched, remote, build, reproducible.
fetched — промежуточное состояние опыта передачи: origin/main обновлена,
а локальная main и её рабочие файлы ещё не сдвинуты.

Восстановление с потерей сделанной учебной работы:
  python3 trainer.py --workspace <каталог-стенда> reset-checkpoint merge --yes
Точки: start, index, branch, merge, recovery, remote, build.
Они создают известное учебное состояние, а не сохраняют ваши решения.

Каталоги стенда: repo/, peer/, remote.git/, .trainer-hooks/.
Корневой маркер: .handbook-git-lab.json; дочерние: .handbook-owned.json.
Не удаляйте и не подменяйте маркеры. Не кладите личные файлы в стенд.
Не запускайте reset одновременно с другими действиями в этих копиях.
Символические ссылки и точки перенаправления каталогов отвергаются.

В созданном repo:
  python3 -m unittest discover -s tests -v
  python3 tools/build.py
Результат: dist/handbook-demo.zip, dist/manifest.json, dist/source-commit.txt.
ZIP содержит только README.txt и app.py. Происхождение вынесено наружу.
Изменения рабочих копий сохраняются между командами trainer.py.
HTTP-служба сама не запускается. Необязательно: python3 app.py --serve.

Самопроверка реализации, со своими временными каталогами:
  python3 check_lab.py
Отчёт: lab-results.json, без абсолютных путей к временным каталогам.
Проверено на Linux с Git 2.43.0. Windows не исполнялся; командный маршрут
главы использует Bash. В Windows возможен python либо py -3 вместо python3.
На рабочем компьютере без разрешённого Git/Python читайте автономную книгу
и используйте её браузерные модели; установка для чтения не нужна.
