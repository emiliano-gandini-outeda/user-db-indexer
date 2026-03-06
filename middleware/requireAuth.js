import jwt from 'jsonwebtoken'

export function requireAuth(req, res, next) {
  const token =
    req.cookies?.ego_token ||
    req.headers.authorization?.replace('Bearer ', '') ||
    req.query.token

  if (!token) return redirectToAuth(res)

  try {
    const payload = jwt.verify(token, process.env.JWT_SECRET)
    req.user = { username: payload.sub }

    if (req.query.token) {
      res.cookie('ego_token', token, { httpOnly: true, sameSite: 'strict' })
      const clean = new URL(req.url, `http://${req.headers.host}`)
      clean.searchParams.delete('token')
      return res.redirect(clean.pathname + clean.search)
    }

    next()
  } catch {
    return redirectToAuth(res)
  }
}

function redirectToAuth(res) {
  res.redirect('https://utils.ego-services.com/auth')
}
