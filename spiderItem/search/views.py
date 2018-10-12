from django.shortcuts import render
from urllib.parse import urlparse

from django.http import HttpResponse
from .models import Spider_url
from spiders.lishipin import download
from spiders.baomihua import main
from spiders.VideoSpiderV1.youtube_spider import Youtubemain

spider_hostname = ['www.youtube.com','www.pearvideo.com',
                   'video.baomihua.com']



def index(request):
    return HttpResponse('Hello,world.You‘re at the search')


def spider_search(request):
    if request.method == "GET":
        status = 1
        return render(request,'home/search.html',context={'status':status})
    elif request.method == "POST":
        url = request.POST.get('url')
        parsed = urlparse(url)
        if parsed.hostname in spider_hostname:
            if parsed.hostname == 'www.youtube.com':
                pname = Youtubemain(url)
            if parsed.hostname == 'www.pearvideo.com':
                pname=download(url)
            if parsed.hostname == 'video.baomihua.com':
                pname = main(url)
        else:
            status = 2
            return render(request,'home/search.html',context={'status':status})

        spider = Spider_url()
        spider.url = url
        spider.save()
        status = 3
    return render(request,'home/search.html',context={'status':status,'pname':pname})



