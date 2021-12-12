import csv
import os

import demjson
import xlrd
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from article.models import Article
from website.views import evaluate
from website.views import token_check
from .forms import WordForm, CharacterForm, PronunciationForm
from .models import Word, Character, Pronunciation, User


@csrf_exempt
def searchWords(request):
    try:
        if request.method == 'GET':
            words = Word.objects.filter(visibility=True)
            if 'contributor' in request.GET:
                words = words.filter(contributor=request.GET['contributor'])
            if 'search' in request.GET:
                result = []
                key = request.GET['search']
                for word in words:
                    score = evaluate(
                        [(word.word, 3), (word.definition, 2), (word.mandarin, 1.5), (word.annotation, 1)], key)
                    result.append((word.id, score))
                result.sort(key=lambda a: a[1], reverse=True)
                words = []
                for id, score in result:
                    if score > 0:
                        words.append(Word.objects.get(id=id))
                    else:
                        break

            words = [word.id for word in words]
            return JsonResponse({"words": words}, status=200)
        elif request.method == 'POST':
            body = demjson.decode(request.body)
            token = request.headers['token']
            user = token_check(token, '***REMOVED***')
            if user:
                body = body['word']
                word_form = WordForm(body)
                if word_form.is_valid() and isinstance(body['mandarin'], list):
                    word = word_form.save(commit=False)
                    word.contributor = user
                    for id in body['related_articles']:
                        Article.objects.get(id=id)
                    for id in body['related_words']:
                        Word.objects.get(id=id)
                    word.save()
                    for id in body['related_articles']:
                        article = Article.objects.get(id=id)
                        word.related_articles.add(article)
                    for id in body['related_words']:
                        wordx = Word.objects.get(id=id)
                        word.related_words.add(wordx)
                    return JsonResponse({'id': word.id}, status=200)
                else:
                    return JsonResponse({}, status=400)
            else:
                return JsonResponse({}, status=401)
        elif request.method == "PUT":
            body = demjson.decode(request.body)
            words = [0] * len(body['words'])
            result = Word.objects.filter(id__in=body['words'])
            a = {}
            num = 0
            for i in body['words']:
                a[i] = num
                num += 1
            for word in result:
                words[a[word.id]] = {'word': {"id": word.id, 'word': word.word, 'definition': word.definition,
                                              "contributor": word.contributor.id, "annotation": word.annotation,
                                              "standard_ipa": word.standard_ipa,
                                              "standard_pinyin": word.standard_pinyin,
                                              "mandarin": eval(word.mandarin) if word.mandarin else [],
                                              "views": word.views},
                                     'contributor': {
                                         'id': word.contributor.id,
                                         'nickname': word.contributor.user_info.nickname,
                                         'avatar': word.contributor.user_info.avatar}}
            result = []
            for item in words:
                if item:
                    result.append(item)
            return JsonResponse({"words": result}, status=200)
        else:
            return JsonResponse({}, status=405)
    except Exception as e:
        return JsonResponse({"msg": str(e)}, status=500)


@csrf_exempt
def manageWord(request, id):
    try:
        word = Word.objects.filter(id=id)
        if word.exists():
            word = word[0]
            if request.method == 'GET':
                related_words = [word.id for word in word.related_words.all()]
                related_articles = [article.id for article in word.related_articles.all()]
                word.views = word.views + 1
                word.save()
                user = word.contributor
                return JsonResponse({"word": {"id": word.id, 'word': word.word, 'definition': word.definition,
                                              "contributor": {"id": user.id, 'username': user.username,
                                                              'nickname': user.user_info.nickname,
                                                              'email': user.email,
                                                              'telephone': user.user_info.telephone,
                                                              'registration_time': user.date_joined.__format__(
                                                                  '%Y-%m-%d %H:%M:%S'),
                                                              'login_time': user.last_login.__format__(
                                                                  '%Y-%m-%d %H:%M:%S') if user.last_login else '',
                                                              'birthday': user.user_info.birthday,
                                                              'avatar': user.user_info.avatar,
                                                              'county': user.user_info.county,
                                                              'town': user.user_info.town,
                                                              'is_admin': user.is_superuser},
                                              "annotation": word.annotation,
                                              "standard_ipa": word.standard_ipa,
                                              "standard_pinyin": word.standard_pinyin,
                                              "mandarin": eval(word.mandarin) if word.mandarin else [],
                                              "related_words": related_words, "related_articles": related_articles,
                                              "views": word.views}}, status=200)
            elif request.method == 'PUT':
                body = demjson.decode(request.body)
                token = request.headers['token']
                if token_check(token, '***REMOVED***', word.contributor.id):
                    body = body['word']
                    word_form = WordForm(body)
                    for key in body:
                        if (key in word_form) and len(word_form[key].errors.data):
                            return JsonResponse({}, status=400)
                    for key in body:
                        if key != 'related_words' and key != 'related_articles':
                            setattr(word, key, body[key])
                        elif key == 'related_words':
                            word.related_words.clear()
                            for id in body['related_words']:
                                wordx = Word.objects.get(id=id)
                                word.related_words.add(wordx)
                        elif key == 'related_articles':
                            word.related_articles.clear()
                            for id in body['related_articles']:
                                article = Article.objects.get(id=id)
                                word.related_articles.add(article)
                    word.save()
                    return JsonResponse({}, status=200)
                else:
                    return JsonResponse({}, status=401)
            elif request.method == 'DELETE':
                token = request.headers['token']
                if token_check(token, '***REMOVED***', word.contributor.id):
                    word.delete()
                    return JsonResponse({}, status=200)
                else:
                    return JsonResponse({}, status=401)
            else:
                return JsonResponse({}, status=405)
        else:
            return JsonResponse({}, status=404)
    except Exception as e:
        return JsonResponse({"msg": str(e)}, status=500)


@csrf_exempt
def searchCharacters(request):
    try:
        if request.method == 'GET':
            characters = Character.objects.all()
            if 'shengmu' in request.GET:
                characters = characters.filter(shengmu=request.GET['shengmu'])
            if 'yunmu' in request.GET:
                characters = characters.filter(yunmu=request.GET['yunmu'])
            if 'shengdiao' in request.GET:
                characters = characters.filter(shengdiao=request.GET['shengdiao'])
            characters = [character.id for character in characters]
            return JsonResponse({"characters": characters}, status=200)
        elif request.method == 'POST':
            body = demjson.decode(request.body)
            token = request.headers['token']
            user = token_check(token, '***REMOVED***', -1)
            if user:
                body = body['character']
                character_form = CharacterForm(body)
                if character_form.is_valid():
                    character = character_form.save(commit=False)
                    character.save()
                    return JsonResponse({'id': character.id}, status=200)
                else:
                    return JsonResponse({}, status=400)
            else:
                return JsonResponse({}, status=401)
        elif request.method == "PUT":
            body = demjson.decode(request.body)
            result = Character.objects.filter(id__in=body['characters'])
            characters = [0] * len(body['characters'])
            a = {}
            num = 0
            for i in body['characters']:
                a[i] = num
                num += 1
            for character in result:
                characters[a[character.id]] = {"id": character.id, 'shengmu': character.shengmu, 'ipa': character.ipa,
                                               'pinyin': character.pinyin, 'yunmu': character.yunmu,
                                               'shengdiao': character.shengdiao,
                                               'character': character.character, 'county': character.county,
                                               'town': character.town}
            result = []
            for item in characters:
                if item:
                    result.append(item)
            return JsonResponse({"characters": result}, status=200)
        else:
            return JsonResponse({}, status=405)
    except Exception as e:
        return JsonResponse({"msg": str(e)}, status=500)


@csrf_exempt
def searchEach(request):
    try:
        if request.method == 'GET':
            search = request.GET['search']
            result = Character.objects.filter(character__in=search)
            dic = {}
            for character in search:
                dic[character] = []
            for character in result:
                dic[character.character].append({"id": character.id, 'shengmu': character.shengmu, 'ipa': character.ipa,
                                                 'pinyin': character.pinyin, 'yunmu': character.yunmu,
                                                 'shengdiao': character.shengdiao, 'character': character.character,
                                                 'county': character.county, 'town': character.town})
            ans = []
            for character in search:
                ans.append({'label': character, 'characters': dic[character]})
            return JsonResponse({'characters': ans}, status=200)
    except Exception as e:
        return JsonResponse({'msg': str(e)}, status=500)


@csrf_exempt
def manageCharacter(request, id):
    try:
        character = Character.objects.filter(id=id)
        if character.exists():
            character = character[0]
            if request.method == 'GET':
                return JsonResponse(
                    {'character': {"id": character.id, 'shengmu': character.shengmu, 'ipa': character.ipa,
                                   'pinyin': character.pinyin, 'yunmu': character.yunmu,
                                   'shengdiao': character.shengdiao,
                                   'character': character.character, 'county': character.county,
                                   'town': character.town}}, status=200)
            elif request.method == 'PUT':
                body = demjson.decode(request.body)
                token = request.headers['token']
                if token_check(token, '***REMOVED***', -1):
                    body = body['character']
                    character_form = CharacterForm(body)
                    for key in body:
                        if len(character_form[key].errors.data):
                            return JsonResponse({}, status=400)
                    for key in body:
                        setattr(character, key, body[key])
                    character.save()
                    return JsonResponse({}, status=200)
                else:
                    return JsonResponse({}, status=401)
            elif request.method == 'DELETE':
                token = request.headers['token']
                if token_check(token, '***REMOVED***', -1):
                    character.delete()
                    return JsonResponse({}, status=200)
                else:
                    return JsonResponse({}, status=401)
            else:
                return JsonResponse({}, status=405)
        else:
            return JsonResponse({}, status=404)
    except Exception as e:
        return JsonResponse({"msg": str(e)}, status=500)


@csrf_exempt
def searchPronunciations(request):
    try:
        if request.method == 'GET':
            if ('token' in request.headers) and token_check(request.headers['token'], '***REMOVED***', -1):
                pronunciations = Pronunciation.objects.all()
            else:
                pronunciations = Pronunciation.objects.filter(visibility=True)
            if 'word' in request.GET:
                pronunciations = pronunciations.filter(word__id=request.GET['word'])
            if 'contributor' in request.GET:
                pronunciations = pronunciations.filter(contributor__id=request.GET['contributor'])
            pronunciations = list(pronunciations)
            pronunciations.sort(key=lambda item: item.id)
            total = len(pronunciations)
            if 'pageSize' in request.GET:
                pageSize = int(request.GET['pageSize'])
                page = int(request.GET['page'])
                r = min(len(pronunciations), page * pageSize)
                l = min(len(pronunciations) + 1, (page - 1) * pageSize)
                pronunciations = pronunciations[l:r]
            result = []
            for pronunciation in pronunciations:
                result.append({'pronunciation': {"id": pronunciation.id, 'word_id': pronunciation.word.id,
                                                 'word_word': pronunciation.word.word, 'source': pronunciation.source,
                                                 'ipa': pronunciation.ipa, 'pinyin': pronunciation.pinyin,
                                                 'contributor': pronunciation.contributor.id,
                                                 'county': pronunciation.county, 'town': pronunciation.town,
                                                 'visibility': pronunciation.visibility},
                               'contributor': {
                                   'id': pronunciation.contributor.id,
                                   'nickname': pronunciation.contributor.user_info.nickname,
                                   'avatar': pronunciation.contributor.user_info.avatar}})
            return JsonResponse({"pronunciation": result, 'total': total}, status=200)
        elif request.method == 'POST':
            token = request.headers['token']
            user = token_check(token, '***REMOVED***')
            if user:
                body = demjson.decode(request.body)
                body = body['pronunciation']
                pronunciation_form = PronunciationForm(body)
                if pronunciation_form.is_valid():
                    pronunciation = pronunciation_form.save(commit=False)
                    pronunciation.word = Word.objects.get(id=body['word'])
                    pronunciation.contributor = user
                    pronunciation.save()
                    return JsonResponse({'id': pronunciation.id}, status=200)
                else:
                    return JsonResponse({}, status=400)
            else:
                return JsonResponse({}, status=401)
        else:
            return JsonResponse({}, status=405)
    except Exception as e:
        return JsonResponse({"msg": str(e)}, status=500)


@csrf_exempt
def combinePronunciation(request, ipa):
    try:
        if request.method == 'GET':
            ipa = str(ipa).strip()
            ans = [(len(p.ipa), p.contributor.username, p.source) for p in Pronunciation.objects.filter(ipa__icontains=ipa)]
            ans.sort(key=lambda x: x[0])
            if len(ans):
                ans = ans[0]
                return JsonResponse({'contributor': ans[1], 'url': ans[2], 'tts': 'null'}, status=200)
            else:
                return JsonResponse({'contributor': 'null', 'url': 'null', 'tts': 'null'}, status=200)
        else:
            return JsonResponse({}, status=405)
    except Exception as e:
        return JsonResponse({"msg": str(e)}, status=500)


@csrf_exempt
def managePronunciation(request, id):
    try:
        pronunciation = Pronunciation.objects.filter(id=id)
        if pronunciation.exists():
            pronunciation = pronunciation[0]
            if request.method == 'GET':
                pronunciation.views += 1
                pronunciation.save()
                user = pronunciation.contributor
                return JsonResponse(
                    {"pronunciation": {"id": pronunciation.id, 'word_id': pronunciation.word.id,
                                       'word_word': pronunciation.word.word, 'source': pronunciation.source,
                                       'ipa': pronunciation.ipa, 'pinyin': pronunciation.pinyin,
                                       'contributor': {"id": user.id, 'username': user.username,
                                                       'nickname': user.user_info.nickname,
                                                       'email': user.email, 'telephone': user.user_info.telephone,
                                                       'registration_time': user.date_joined.__format__(
                                                           '%Y-%m-%d %H:%M:%S'),
                                                       'login_time': user.last_login.__format__('%Y-%m-%d %H:%M:%S')
                                                       if user.last_login else '',
                                                       'birthday': user.user_info.birthday,
                                                       'avatar': user.user_info.avatar,
                                                       'county': user.user_info.county, 'town': user.user_info.town,
                                                       'is_admin': user.is_superuser}, 'county': pronunciation.county,
                                       'town': pronunciation.town, 'visibility': pronunciation.visibility}}, status=200)
            elif request.method == 'PUT':
                token = request.headers['token']
                if token_check(token, '***REMOVED***', pronunciation.contributor.id):
                    body = demjson.decode(request.body)
                    body = body['pronunciation']
                    pronunciation_form = PronunciationForm(body)
                    for key in body:
                        if (key != 'word') and len(pronunciation_form[key].errors.data):
                            return JsonResponse({}, status=400)
                    for key in body:
                        if key != 'word':
                            setattr(pronunciation, key, body[key])
                        else:
                            pronunciation.word = Word.objects.get(id=body[key])
                    pronunciation.save()
                    return JsonResponse({}, status=200)
                else:
                    return JsonResponse({}, status=401)
            elif request.method == 'DELETE':
                token = request.headers['token']
                if token_check(token, '***REMOVED***'):
                    pronunciation.delete()
                    return JsonResponse({}, status=200)
                else:
                    return JsonResponse({}, status=401)
            else:
                return JsonResponse({}, status=405)
        else:
            return JsonResponse({}, status=404)
    except Exception as e:
        return JsonResponse({"msg": str(e)}, status=500)


@require_POST
@csrf_exempt
def load_character(request):
    try:
        body = demjson.decode(request.body)
        file = body['file']
        sheet = xlrd.open_workbook(os.path.join('material', 'character', file)).sheet_by_index(0)
        line = sheet.nrows
        col = sheet.ncols
        title = sheet.row(0)
        for line in range(1, line):
            info = sheet.row(line)
            dic = {}
            for i in range(col):
                dic[title[i].value] = info[i].value
            character_form = CharacterForm(dic)
            if character_form.is_valid():
                character = character_form.save(commit=True)
                if character.id % 100 == 0:
                    print('load character {}'.format(character.id))
            else:
                raise Exception('add fail in {}'.format(dic))
            return JsonResponse({}, status=200)
    except Exception as e:
        return JsonResponse({"msg": str(e)}, status=500)


@require_POST
@csrf_exempt
def load_word(request):
    try:
        body = demjson.decode(request.body)
        file = body['file']
        sheet = open(os.path.join('material', 'word', file))
        lines = sheet.readlines()
        title = ['word', 'definition']
        col = 2
        for line in lines:
            info = line.split(',', 1)
            dic = {}
            for i in range(col):
                dic[title[i]] = info[i] if info[i] else '【待更新】'
            word_form = WordForm(dic)
            if word_form.is_valid():
                word = word_form.save(commit=False)
                word.contributor = User.objects.get(username='root')
                word.save()
                if word.id % 100 == 0:
                    print('load character {}'.format(word.id))
            else:
                raise Exception('add fail in {}'.format(dic))
        return JsonResponse({}, status=200)
    except Exception as e:
        return JsonResponse({"msg": str(e)}, status=500)


@csrf_exempt
def record(request):
    if request.method == 'GET':
        words = [{'word': word.id, 'ipa': word.standard_ipa, 'pinyin': word.standard_pinyin,
                  'count': word.pronunciation.count(), 'item': word.word, 'definition': word.definition}
                 for word in Word.objects.all() if word.standard_ipa and word.standard_pinyin]
        pageSize = int(request.GET['pageSize']) if 'pageSize' in request.GET else 15
        page = int(request.GET['page']) if 'page' in request.GET else 15
        r = min(len(words), page * pageSize)
        l = min(len(words) + 1, (page - 1) * pageSize)
        words = words
        return JsonResponse({
            'records': words[l:r],
            "total": {
                "item": len(words),
                "page": (len(words) - 1) // pageSize + 1
            }
        }, status=200)
    else:
        return JsonResponse({}, status=405)


@csrf_exempt
def upload_standard(request):
    '''
    通过excel上传word的standard_pinyin，standard_ipa，分为三列，为别为id,pinyin,ipa，有表头
    :return: 返回名为conflict的csv，展示与数据库冲突的word字段，为5列，id,init_ipa,init_pinyin,ipa,pinyin
    '''
    try:
        if request.method == 'POST':
            token = request.headers['token']
            user = token_check(token, '***REMOVED***', -1)
            if user:
                file = request.FILES.get("file")

                sheet = xlrd.open_workbook(file_contents=file.read()).sheet_by_index(0)  # 错误
                line = sheet.nrows
                col = sheet.ncols
                ids = [int(x.value) for x in sheet.col(0)[1:]]
                words = sorted(list(Word.objects.filter(id__in=ids)), key=lambda w: w.id)

                # 将输入excel的词条按id从小到大排序
                infos = []
                for i in range(1, line):
                    info = sheet.row(i)
                    infos.append([int(info[0].value), info[1:]])
                infos.sort(key=lambda a: a[0])

                def conflict(x, y):
                    return x and y and x != y

                conflicts = []
                j = 0
                for i in range(line):
                    while j < len(words) and words[j].id < infos[i][0]:
                        j += 1
                    if j < len(words) and words[j].id == infos[i][0]:
                        if conflict(words[j].standard_ipa, infos[i][1][1].value) or \
                                conflict(words[j].standard_pinyin, infos[i][1][0].value):
                            conflicts.append(
                                [words[j].id, words[j].standard_ipa, words[j].standard_pinyin,
                                 infos[i][1][1].value, infos[i][1][0].value])
                        words[j].standard_ipa = infos[i][1][1].value
                        words[j].standard_pinyin = infos[i][1][0].value
                        words[j].save()
                        j += 1
                        if j % 100 == 0:
                            print(j)

                response = HttpResponse(content_type='text/csv', status=200, encoding='ANSI')
                response["Content-Disposition"] = "attachment; filename=conflict.csv"
                title = ['单词ID', '原IPA', '原拼音', '现IPA', '现拼音']
                file = csv.writer(response)
                file.writerow(title)
                file.writerows(conflicts)
                return response
            else:
                return JsonResponse({}, status=401)
        else:
            return JsonResponse({}, status=405)
    except Exception as e:
        return JsonResponse({'msg': str(e)}, status=500)
