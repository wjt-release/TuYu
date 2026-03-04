from datetime import datetime
from flask import render_template, session, redirect, url_for, flash, abort, request, current_app, make_response
from flask_login import login_required, current_user
from . import main
from .forms import EditProfileForm, NameForm, PostForm
from .. import db
from ..models import Permission, User, Post
from ..decorators import admin_required, permission_required
from .pics import picData
import os

# 刚进网站的主页
@main.route('/', methods=['GET', 'POST'])
def index():
    
    if request.method == 'POST' and request.files['choose-img'] is not None:
        id = picData.addPicture(current_user.id)
        base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        filename = os.path.join(base_path, 'static', 'save', str(id) + '.png')
        print(filename)
        img = request.files['choose-img']
        img.save(filename)
        return redirect(url_for('.new', id=id))

    if not current_user.is_authenticated:
        return redirect(url_for('auth.login'))

    print('###')
    print(current_user.id)

    form = PostForm()
    if current_user.can(Permission.WRITE) and form.validate_on_submit():
        post = Post(body=form.body.data, author=current_user._get_current_object())
        db.session.add(post)
        db.session.commit()
        return redirect(url_for('.index'))
    page = request.args.get('page', 1, type=int)
    show_followed = False
    if current_user.is_authenticated:
        show_followed = bool(request.cookies.get('show_followed', ''))
    if show_followed:
        query = current_user.followed_posts
    else:
        query = Post.query
    pagination = query.order_by(Post.timestamp.desc()).paginate(
        page, per_page=current_app.config['HAMBLOGER_POSTS_PER_PAGE'],
        error_out=False)
    posts = pagination.items
    edit_post = Post.query.order_by(Post.id.desc()).first()
    return render_template('index.html', form=form, posts=posts,
                           show_followed=show_followed, pagination=pagination, edit_post=edit_post)


@main.route('/all')
@login_required
def show_all():
    resp = make_response(redirect(url_for('.index')))
    resp.set_cookie('show_followed', '', max_age=30 * 24 * 60 * 60)  # 30天
    return resp


@main.route('/followed')
@login_required
def show_followed():
    resp = make_response(redirect(url_for('.index')))
    resp.set_cookie('show_followed', '1', max_age=30 * 24 * 60 * 60)  # 30天
    return resp


@main.route('/post/<int:id>')
def post(id):
    post = Post.query.get_or_404(id)
    edit_post = Post.query.order_by(Post.id.desc()).first()
    return render_template('post.html', posts=[post],
                           edit_post=edit_post)


@main.route('/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit(id):
    post = Post.query.get_or_404(id)
    if current_user != post.author and \
            not current_user.can(Permission.ADMIN):
        abort(403)
    form = PostForm()
    if form.validate_on_submit():
        post.body = form.body.data
        db.session.add(post)
        db.session.commit()
        flash('更新成功。')
        return redirect(url_for('.post', id=post.id))
    form.title.data = post.title
    form.sub_title.data = post.sub_title
    form.body.data = post.body
    edit_post = Post.query.order_by(Post.id.desc()).first()
    return render_template('edit_post.html', form=form, posts=[post], edit_post=edit_post)

# 新建图片描述的页面
@main.route('/new/<int:id>', methods=['GET', 'POST'])
@login_required
def new(id):
    if request.method == 'POST' and request.form['describe'] is not None:
        picData.setDescribe(id, request.form['describe'])
        return redirect(url_for('.detail', id=id))
    page = request.args.get('page', 1, type=int)
    show_followed = False
    if current_user.is_authenticated:
        show_followed = bool(request.cookies.get('show_followed', ''))
    pagination = Post.query.order_by(Post.timestamp.desc()).paginate(
        page, per_page=current_app.config['HAMBLOGER_POSTS_PER_PAGE'],
        error_out=False)
    posts = pagination.items
    edit_post = Post.query.order_by(Post.id.desc()).first()
    return render_template('new.html', img_id=id)

@main.route('/detail/<int:id>', methods=['GET', 'POST'])
@login_required
def detail(id):
    simpics = picData.calcSimilar(id)
    print(simpics)
    return render_template('detail.html', simpics=simpics)

@main.route('/picture/<int:id>', methods=['GET', 'POST'])
@login_required
def picture(id):
    stared = picData.isStared(current_user.id, id)
    owned = picData.isOwner(current_user.id, id)
    owner = picData.getOwner(id)
    ownername = User.query.filter_by(id=owner).first().username
    return render_template('picture.html', star=stared, own=owned, id=id, owner=owner, own_num=picData.getOwnPictureNum(owner), star_num=picData.getStarPictureNum(owner), ownername=ownername, describe=picData.getDescribe(id))

user_star_list = False
@main.route('/type/<username>?<int:status>')
def type(username, status):
    global user_star_list
    if status == 0:
        user_star_list = False
    else:
        user_star_list = True
    return redirect(url_for('.user', username=username))

# 用户个人主页
@main.route('/user/<username>')
def user(username):
    user = User.query.filter_by(username=username).first()
    if user is None:
        abort(404)
    posts = user.posts.order_by(Post.timestamp.desc()).all()
    edit_post = Post.query.order_by(Post.id.desc()).first()
    page = request.args.get('page', 1, type=int)
    pagination = user.posts.order_by(Post.timestamp.desc()).paginate(
        page, per_page=current_app.config['HAMBLOGER_POSTS_PER_PAGE'],
        error_out=False)
    global user_star_list
    if not user_star_list:
        pics = picData.getOwnPicture(user.id)
    else:
        pics = picData.getStarPicture(user.id)
    return render_template('user.html', user=user, posts=posts, endpoint='.user', pagination=pagination, edit_post=edit_post, haspics=pics)

@main.route('/star/<int:id>')
@login_required
def star(id):
    if not picData.isStared(current_user.id, id):
        picData.addStar(id, current_user.id)
    return redirect(url_for('.picture', id=id))

@main.route('/unstar/<int:id>')
@login_required
def unstar(id):
    if picData.isStared(current_user.id, id):
        picData.delStar(id, current_user.id)
    return redirect(url_for('.picture', id=id))

# 编辑个人资料
@main.route('/edit-profile', methods=['GET', 'POST'])
@login_required
def edit_profile():
    form = EditProfileForm()
    if form.validate_on_submit():
        f = form.mask.data
        filename = (str(current_user.id) + '.png')
        if (f is not None):
            f.save(os.path.join('app/static/mask/',filename))
        current_user.name = form.name.data
        current_user.location = form.location.data
        current_user.about_me = form.about_me.data
        db.session.add(current_user._get_current_object())
        db.session.commit()
        flash('你的个人资料已更新')
        return redirect(url_for('.user', username=current_user.username))
    form.name.data = current_user.name
    form.location.data = current_user.location
    form.about_me.data = current_user.about_me
    edit_post = Post.query.order_by(Post.id.desc()).first()
    return render_template('edit_profile.html', form=form, edit_post=edit_post)


# 关注 的路由相应
@main.route('/follow/<username>')
@login_required
@permission_required(Permission.FOLLOW)
def follow(username):
    user = User.query.filter_by(username=username).first()
    if user is None:
        flash('用户无效')
        return redirect(url_for('.index'))
    if current_user.is_following(user):
        flash('你已经关注Ta了')
        return redirect(url_for('.user', username=username))
    current_user.follow(user)
    db.session.commit()
    flash('你刚刚关注了 %s.' % username)
    return redirect(url_for('.user', username=username))


# 取消关注
@main.route('/unfollow/<username>')
@login_required
@permission_required(Permission.FOLLOW)
def unfollow(username):
    user = User.query.filter_by(username=username).first()
    if user is None:
        flash('用户无效')
        return redirect(url_for('.index'))
    if not current_user.is_following(user):
        flash('你本来就没有关注Ta')
        return redirect(url_for('.user', username=username))
    current_user.unfollow(user)
    db.session.commit()
    flash('你刚刚取消了对 %s 的关注' % username)
    return redirect(url_for('.user', username=username))


# 关注者 的路由
@main.route('/followers/<username>')
def followers(username):
    user = User.query.filter_by(username=username).first()
    if user is None:
        flash('用户无效')
        return redirect(url_for('.index'))
    page = request.args.get('page', 1, type=int)
    pagination = user.followers.paginate(
        page, per_page=current_app.config['HAMBLOGER_FOLLOWERS_PER_PAGE'],
        error_out=False)
    follows = [{'user': item.follower, 'timestamp': item.timestamp}
               for item in pagination.items]
    edit_post = Post.query.order_by(Post.id.desc()).first()
    return render_template('followers.html', user=user, title="Followers of",
                           endpoint='.followers', pagination=pagination,
                           follows=follows, edit_post=edit_post)


# 有谁在关注Ta
@main.route('/followed_by/<username>')
def followed_by(username):
    user = User.query.filter_by(username=username).first()
    if user is None:
        flash('用户无效')
        return redirect(url_for('.index'))
    page = request.args.get('page', 1, type=int)
    pagination = user.followed.paginate(
        page, per_page=current_app.config['HAMBLOGER_FOLLOWERS_PER_PAGE'],
        error_out=False)
    follows = [{'user': item.followed, 'timestamp': item.timestamp}
               for item in pagination.items]
    edit_post = Post.query.order_by(Post.id.desc()).first()
    return render_template('followers.html', user=user, title="Followed by",
                           endpoint='.followed_by', pagination=pagination,
                           follows=follows, edit_post=edit_post)


@main.route('/game')
def game():
    return render_template('game.html')
