"""dailyfresh URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/1.8/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  url(r'^$', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  url(r'^$', Home.as_view(), name='home')
Including another URLconf
    1. Add an import:  from blog import urls as blog_urls
    2. Add a URL to urlpatterns:  url(r'^blog/', include(blog_urls))
"""
from django.conf.urls import url
from django.contrib.auth.decorators import login_required

# from user import views
from user.views import RegisterView, LoginView, ActiveView, UserInfoView, UserOrderView, AddressView, LogoutView

urlpatterns = [
    # url(r'^register$', views.register, name='register'),  # 注册界面
    # url(r'^register_handle$', views.register_handle, name='register_handle'),  # 注册处理
    url(r'^register$', RegisterView.as_view(), name='register'),
    url(r'^active/(?P<token>.*)$', ActiveView.as_view(), name='active'),
    url(r'^login$', LoginView.as_view(), name='login'),  # 登录页面
    url(r'^logout$', LogoutView.as_view(), name='logout'), # 注销登录
    # url(r'^$', login_required(UserInfoView.as_view()), name='user'), # 用户中心信息页
    # url(r'^order$', login_required(UserOrderView.as_view()), name='order'),#用户中心订单页
    # url(r'^address$', login_required(AddressView.as_view()), name='address'),# 用户中心地址页面
    url(r'^$', UserInfoView.as_view(), name='user'),  # 用户中心信息页
    url(r'^order$', UserOrderView.as_view(), name='order'),  # 用户中心订单页
    url(r'^address$', AddressView.as_view(), name='address'),  # 用户中心地址页面

]
