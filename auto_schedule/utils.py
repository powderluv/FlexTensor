import os
import time
import tvm
import numpy as np
import math


def to_int(expr):
    try:
        res = int(expr)
    except Exception as e:
        raise RuntimeError("fail to convert to int: %s" % str(e))
    return res


def to_tuple(expr_tuple):
    return tuple([to_int(x) for x in expr_tuple])


def int_to_lst(value, bit=32, base=10):
    assert isinstance(value, int)
    ret = [0] * bit
    cur = 0
    if value < 0:
        f = -1
        value = -value
    else:
        f = 1
    while value != 0:
        r = value % base
        value = value // base
        ret[cur] = r * f
        cur += 1
    return ret


def powerx_lst(x, left, right):
    ret = []
    beg = left
    while not is_power_of_x(x, beg):
        beg += 1
    while beg < right:
        ret.append(beg)
        beg = beg * x
    return ret


def get_factor_lst(value):
    assert isinstance(value, int)
    ret = []
    end = math.sqrt(value)
    for i in range(1, math.ceil(end)):
        if value % i == 0:
            ret.append(i)
            ret.append(value // i)
    if end - int(end) < 1e-10 and value % int(end) == 0:
        ret.append(int(end))

    return ret


def split_part_names(original, parts):
    assert isinstance(original, str) and isinstance(parts, int)
    ret = [original + "." + str(i) for i in range(parts)]
    return ret


def str_to_tuple(s):
    assert isinstance(s, str)
    s = s.strip()
    s = s[1:-1]
    s = s.split(", ")
    ret = []
    for v in s:
        ret.append(int(v))
    return tuple(ret)


def any_factor_split(value, number, allow_non_divisible='off'):
    assert allow_non_divisible in ['off', 'power2', 'continuous']
    ret = []
    assert_print(isinstance(number, int))
    recursive_factor_split(value, [], number, ret, allow_non_divisible)
    return ret


def recursive_factor_split(left, cur, number, ret, policy):
    if number == 1:
        ret.append(cur + [left])
        return
    if policy == 'power2':
        f_lst = get_factor_lst(left)
        f_lst.extend(powerx_lst(2, 1, left))
        f_lst = list(sorted(list(set(f_lst))))
    elif policy == 'continuous':
        f_lst = list(range(1, left + 1))
    else:
        f_lst = get_factor_lst(left)
        f_lst = list(sorted(f_lst))
    for f in f_lst:
        recursive_factor_split(math.ceil(left / f), cur + [f], number - 1, ret, policy)


def three_factor_split(value):
    assert isinstance(value, int)
    ret = []
    for i in range(1, value+1):
        if value % i == 0:
            res = value // i
            factor_lst = get_factor_lst(res)
            for factor in factor_lst:
                ret.append((i, factor, res // factor))
    return ret


def two_factor_split(value):
    assert isinstance(value, int)
    ret = []
    for i in range(1, value+1):
        if value % i == 0:
            ret.append((i, value // i))
    return ret


def dev(input):
    import torch
    m = torch.mean(input, dim=-1)
    return torch.pow(torch.sum(torch.pow(input - m, 2)), 0.5)


def _dfs_interleave(cur, la, lb, pa, pb, enda, endb, res):
    tmp = []
    if pa == enda:
        while pb != endb:
            tmp.append(lb[pb])
            pb += 1
        res.append(cur + tmp)
        return
    if pb == endb:
        while pa != enda:
            tmp.append(la[pa])
            pa += 1
        res.append(cur + tmp)
        return
    _dfs_interleave(cur + [la[pa]], la, lb, pa + 1, pb, enda, endb, res)
    _dfs_interleave(cur + [lb[pb]], la, lb, pa, pb + 1, enda, endb, res)
    return


def interleave(la, lb):
    enda = len(la)
    endb = len(lb)
    res = []
    pa, pb = 0, 0
    cur = []
    _dfs_interleave(cur, la, lb, pa, pb, enda, endb, res)
    return res


def _dfs_premute(cur, lst, used, length, use_num, res):
    if use_num == length:
        res.append(cur)
        return
    for i in range(length):
        if not used[i]:
            used[i] = True
            _dfs_premute(cur + [lst[i]], lst, used, length, use_num + 1, res)
            used[i] = False
    return


def permute(lst):
    res = []
    length = len(lst)
    used = [False for i in range(length)]
    cur = []
    use_num = 0
    _dfs_premute(cur, lst, used, length, use_num, res)
    return res


def gumbel_softmax(logits):
    import torch
    from torch.autograd import Variable
    epsilon = 1e-20
    G = torch.rand_like(logits)
    y = logits + -Variable(torch.log(-torch.log(G + epsilon) + epsilon))
    soft_y = torch.softmax(y, dim=-1)
    _, index = soft_y.max(dim=-1)
    hard_y = torch.zeros_like(soft_y).view(-1, soft_y.shape[-1])
    hard_y.scatter_(1, index.view(-1, 1), 1)
    hard_y = hard_y.view(*soft_y.shape)
    return soft_y + (hard_y - soft_y).detach()


def parted_linear(x, left, right):
    import torch
    if left > right:
        tmp = left
        left = right
        right = tmp
    return torch.relu(right - torch.relu(right - x) - left) + left


def _dfs_gen_enum(cur, cur_len, elements, length, res):
    if cur_len == length:
        res.append(cur)
        return
    for ele in elements:
        _dfs_gen_enum(cur + [ele], cur_len + 1, elements, length, res)
    return


def gen_enum(elements, length):
    res = []
    cur = []
    cur_len = 0
    _dfs_gen_enum(cur, cur_len, elements, length, res)
    return res


def _dfs_gen_group(cur, elements, p, length, left_groups, res, padding):
    if left_groups == 1:
        res.append(cur + [length] * (1 + padding))
    elif left_groups > 1:
        # _dfs_gen_group(cur, elements, p, length, left_groups-1, res)
        for i in range(p + 1, length):
            _dfs_gen_group(cur + [i], elements, i, length, left_groups-1, res, padding)
    else:
        raise RuntimeError("At least 1 group")
            


def gen_group(elements, most_groups=3):
    res = []
    length = len(elements)
    lower = min(length, most_groups)
    upper = min(length, most_groups)
    for groups in range(lower, upper + 1):
        _dfs_gen_group([], elements, 0, length, groups, res, most_groups - groups)
    return res


def fact(n):
    if n <= 0:
        return 1
    return n * fact(n - 1)


def comb(m, n):
    assert m >= n
    return fact(m) // (fact(n) * fact(m - n))


def is_power_of_x(x, val):
    assert isinstance(val, int) and val > 0
    return math.fabs(math.pow(x, int(math.log(val, x))) - val) < 1e-20


def nearest_power_of_two(val):
    assert isinstance(val, int) and val > 0
    return int(math.pow(2, int(math.log2(val))))


def test_allclose(value, target, rtol=1e-5, print_diff=False):
    passed = 1
    try:
        tvm.testing.assert_allclose(value, target, rtol)
    except AssertionError:
        passed = 0
        if print_diff:
            print(target - value)
            print("Max diff:", np.max(np.fabs(target - value)))
    return passed


def assert_print(bool_stmt, false_str=""):
    if not bool_stmt:
        raise AssertionError(false_str)


def free_cuda():
    import torch
    ret = []
    if torch.cuda.is_available():
        filename = "auto_schedule_check_cuda_free_memory_{}".format(time.time())
        os.system("nvidia-smi -q -d Memory | grep -A4 GPU | grep Free > {}".format(filename))
        memory_gpu = list(filter(lambda x: x[0] > 0, [(int(x.split()[2]), i) for i, x in enumerate(open(filename, 'r').readlines())]))
        memory_gpu = sorted(memory_gpu, key=lambda x: x[0], reverse=True)
        os.remove(filename)
        return [x[1] for x in memory_gpu]
    return ret



def test_three_factor_split():
    values = [16, 256, 512, 24, 3, 1024, 2048, 4096]
    for v in values:
        print(len(three_factor_split(v)))


def test_interleave():
    la = ["none", "rx", "ry", "rc"]
    lb = ["bi", "hi", "wi", "ci"]
    res = interleave(la, lb)
    print("length={}".format(len(res)))
    for ele in res:
        print(ele)


def test_permute():
    lst = ["b", "k", "x", "y"]
    res = permute(lst)
    print("length={}".format(len(res)))
    for ele in res:
        print(ele)


def test_gen_enum():
    elements = [True, False]
    length = 4
    res = gen_enum(elements, length)
    print("length={}".format(len(res)))
    for ele in res:
        print(ele)


def test_gen_group():
    elements = ['x', 'y', 'z', 'w']
    res = gen_group(elements)
    print("length={}".format(len(res)))
    for ele in res:
        print(ele)


def test_any_factor_split():
    ret = any_factor_split(448, 4, 'power2')
    print(ret)
    print("length=", len(ret))


if __name__ == "__main__":
    test_any_factor_split()
