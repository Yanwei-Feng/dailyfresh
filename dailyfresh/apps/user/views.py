from django.shortcuts import render, redirect
from django.urls import reverse
from django.http import HttpResponse
from django.core.mail import send_mail
from django.contrib.auth import authenticate, login, logout
import re
from user.models import User, Address
from goods.models import GoodsSKU
from django.views.generic import View
from itsdangerous import TimedJSONWebSignatureSerializer as Serializer
from itsdangerous import SignatureExpired

from django.conf import settings
from celery_tasks.tasks import send_register_activat_email
from utils.mixin import LoginRequiredMixin
from django_redis import get_redis_connection



#类视图

class RegisterView(View):
    """注册"""
    def get(self, request):
        """显示注册页面"""
        return render(request, 'register.html')

    def post(self, request):
        """进行注册处理"""
        # 1. 接收数据
        username = request.POST.get('user_name')

        password = request.POST.get('pwd')

        email = request.POST.get('email')

        allow = request.POST.get('allow')

        # 2. 进行数据校验
        if not all([username, password, email]):
            # 数据不完整
            return render(request, 'register.html', {'errmsg': '数据不完整'})

        # 校验邮箱
        if not re.match(r'^[a-z0-9][\w\.\-]*@[a-z0-9\-]+(\.[a-z]{2,5}){1,2}$', email):
            return render(request, 'register.html', {'errmsg': '邮箱格式不正确'})

        if allow != 'on':
            return render(request, 'register.html', {'errmsg': '请同意协议'})

        # 校验用户名是否重复
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            # 用户名不存在
            user = None

        if user:
            # 用户名已存在
            return render(request, 'register.html', {'errmsg': '用户名已存在'})
        # 3. 进行业务处理:进行用户注册
        user = User.objects.create_user(username, email, password)
        user.is_active = 0
        user.save()

        # 发送激活邮件，包含激活链接：http://127.0.0.1:8000/user/active/1
        # 激链接中需要包含用户的身份信息,并且要把身份信息加密
        # 加密用户的身份信息, 生成激活的token

        ser = Serializer(settings.SECRET_KEY, 3600)
        info = {'confirm': user.id}
        token = ser.dumps(info)
        token = token.decode()

        # 发邮件
        send_register_activat_email.delay(email, username, token)
        # subject = '天天生鲜欢迎信息'
        # message = ''
        # sender = settings.EMAIL_FROM
        # receiver = [email]
        # html_message = '<h1>%s,欢迎您成为天天生鲜注册会员</h1>请点击下面链接激活您的账号<br /><a href="http://127.0.0.1:8000/user/active/%s">http://127.0.0.1:8000/user/active/%s</a>' % (
        #     username, token, token)
        # # 阻塞
        # send_mail(subject, message, sender, receiver, html_message=html_message)
        # 4. 返回应答, 跳转到首页
        return redirect(reverse('goods:index'))


class ActiveView(View):
    """用户激活"""
    def get(self, request, token):
        """进行用户激活"""
        # 进行解密， 获取要激活的用户信息
        serializer = Serializer(settings.SECRET_KEY, 3600)
        try:
            info = serializer.loads(token)
            # 获取待激活用户的id
            user_id = info['confirm']
            # 根据id 获取用户信息
            user = User.objects.get(id=user_id)
            user.is_active = 1
            user.save()

            # 返回应答

            return redirect(reverse("user:login"))
        except SignatureExpired as e:
            # 激活链接已过期
            return HttpResponse("激活链接已过期")

class LoginView(View):
    def get(self, request):
        """显示登录页面"""
        # 判断是否记住了用户名
        if 'username' in request.COOKIES:
            username = request.COOKIES.get('username')
            checked = 'checked'
        else:
            username = ''
            checked = ''
        return render(request, 'login.html', {'username':username, 'checked':checked})

    def post(self, request):
        """登录校验"""
        # 接收数据
        username = request.POST.get('username')
        password = request.POST.get('pwd')

        # 校验数据
        if not all([username, password]):
            return render(request, 'login.html', {'errmsg':'数据不完整'})

        user = authenticate(username=username, password=password)
        if user is not  None:
            # 用户名或密码正确
            if user.is_active:
                # 用户已激活
                # 记录用户的登录状态
                login(request, user)

                # 获取登录后跳转到的地址
                next_url = request.GET.get('next', reverse('goods:index'))

                # 判断是否要记住 用户名
                response = redirect(next_url)
                remember = request.POST.get('remember')
                if remember == 'on':
                    # 记住用户名
                    print(username)
                    response.set_cookie('username', username, max_age=7*24*3600)
                else:
                    response.delete_cookie('username')
                return response
            else:
                # 用户未激活
                return render(request, 'login.html', {'errmsg':"账户未激活"})
        else:
            # 用户名或密码错误
            return render(request, 'login.html', {'errmsg':'用户名或密码错误'})

        # 业务处理：登录校验


# /user/logout
class LogoutView(View):
    '''退出登录'''
    def get(self, request):
        '''退出登录'''
        # 清除用户的session信息
        logout(request)

        # 跳转到首页
        return redirect(reverse('goods:index'))



# /user
class UserInfoView(LoginRequiredMixin,View):
    """用户中心信息页"""
    def get(self, request):
        """显示"""
        # 获取用户的个人信息
        user = request.user
        address = Address.objects.get_default_address(user)
        # 获取用户的历史浏览记录
        # from redis import StrictRedis
        #
        # redis = StrictRedis(host='127.0.0.1', port=6379, db='9')
        con = get_redis_connection('default')
        #  取用户的浏览记录
        history_key = 'history_%d'%user.id
        # 获取用户最新浏览的5个商品的id
        sku_ids = con.lrange(history_key, 0, 4)
        # 从数据库中查询用户浏览的商品的具体信息
        # goods_li = GoodsSku.objects.filter(id__in=sku_ids)
        # 遍历获取用户浏览的历史商品信息
        goods_li = []
        for id in sku_ids:
            goods = GoodsSku.objects.get(id=id)
            goods_li.append(goods)

        #组织上下文
            goods = {'page':'user',
                   'address':address,
                   'goods_li':goods_li}
        # page='user'
        return render(request, 'user_center_info.html', goods)

# /user/order
class UserOrderView(LoginRequiredMixin,View):
    """用户中心订单页"""
    def get(self, request):
        """显示"""
        # 获取用户的订单信息

        #page='order'
        return render(request, 'user_center_order.html', {'page':'order'})

# /user/address
class AddressView(LoginRequiredMixin,View):
    """用户中心地址页"""
    def get(self, request):
        """显示"""
        # 获取用户的默认收货地址
        # 获取登录用户对应的user对象
        user = request.user
        address = Address.objects.get_default_address(user)
        # try:
        #     address = Address.objects.get(user=user, is_default=True)
        # except Address.DoesNotExist:
        #     # 不存在默认收货地址
        #     address = None

        # 使用模板
        #page='address'
        return render(request, 'user_center_site.html', {'page':'address', 'address':address})

    def post(self, request):
        """地址的添加"""
        # 1.接收数据
        receiver = request.POST.get('receiver')
        addr = request.POST.get("addr")
        zip_code = request.POST.get("zip_code")
        phone = request.POST.get("phone")

        # 2.校验数据
        if not all([receiver, addr, phone]):
            return render(request,'user_center_site.html', {'errmsg':"数据不完整"})
        # 校验手机号
        if not re.match(r'^1[3|4|5|7|8][0-9]{9}$',phone):
            return render(request, 'user_center_site.html', {'errmsg':'手机格式不正确'})
        # 3.业务处理:地址添加
        # 如果用户已存在默认收货地址，添加的地址不作为默认收货地址，否则作为默认收货地址
        # 获取登录用户对应的user对象
        user = request.user
        address = Address.objects.get_default_address(user)
        # try:
        #     address = Address.objects.get(user=user, is_default=True)
        # except Address.DoesNotExist:
        #     # 不存在默认收货地址
        #     address = None

        if address:
            is_default = False
        else:
            is_default = True

        #添加地址
        Address.objects.create(user = user,
                               receiver = receiver,
                               addr = addr,
                               zip_code=zip_code,
                               phone=phone,
                               is_default=is_default,
                               )

        # 4. 返回视图
        return  redirect(reverse('user:address'))  # get请求方式
# Create your views here.

# /user/register
def register(request):
    """注册"""
    if request.method == 'GET':
        return render(request, 'register.html', {})
    else:
        # 1. 接收数据
        username = request.POST.get('user_name')

        password = request.POST.get('pwd')

        email = request.POST.get('email')

        allow = request.POST.get('allow')

        # 2. 进行数据校验
        if not all([username, password, email]):
            # 数据不完整
            return render(request, 'register.html', {'errmsg': '数据不完整'})

        # 校验邮箱
        if not re.match(r'^[a-z0-9][\w\.\-]*@[a-z0-9\-]+(\.[a-z]{2,5}){1,2}$', email):
            return render(request, 'register.html', {'errmsg': '邮箱格式不正确'})

        if allow != 'on':
            return render(request, 'register.html', {'errmsg': '请同意协议'})

        # 校验用户名是否重复
        try:
            User.objects.get(username=username)
        except User.DoesNotExist:
            # 用户名不存在
            user = None

        if user:
            # 用户名已存在
            return render(request, 'register.html', {'errmsg': '用户名已存在'})
        # 3. 进行业务处理:进行用户注册
        user = User.objects.create_user(username, email, password)
        user.is_active = 0
        user.save()

        # 4. 返回应答, 跳转到首页
        return redirect(reverse('goods:index'))


# /user/register_handle
def register_handle(request):
    """进行注册处理"""

    # return render(request, 'index.html', {})
