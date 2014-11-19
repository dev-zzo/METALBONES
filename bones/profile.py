import pstats
p = pstats.Stats('profile.data')
p.strip_dirs().sort_stats(-1).print_stats()
