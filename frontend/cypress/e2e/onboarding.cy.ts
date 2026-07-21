/// <reference types="cypress" />

// The magic-link identity flow: request a link, land back with ?token=, then
// either sign straight in (returning email) or finish signup (new email).

const maya = { id: 1, username: 'maya', avatar_url: '/media/avatars/maya.png', is_bot: false }

function stubCreatePost(author: typeof maya) {
  cy.intercept('POST', '/api/posts', {
    statusCode: 200,
    body: {
      id: 99,
      body: 'hello there',
      created_at: '2026-07-06T12:00:00Z',
      author,
      like_count: 0,
      comment_count: 0,
      top_comments: [],
      human_share: 1,
      human_messages: 1,
      bot_messages: 0,
      total_messages: 1,
    },
  }).as('createPost')
  // The feed the app loads immediately after identity resolves.
  cy.intercept('GET', '/api/posts*', { statusCode: 200, body: [] }).as('feed')
}

describe('onboarding', () => {
  beforeEach(() => {
    // No session cookie yet — every spec here starts at the email gate.
    cy.intercept('GET', '/api/auth/me', { statusCode: 401, body: { error: 'Not logged in.' } }).as('me')
  })

  it('requests a magic link for an email and shows the "check your email" step', () => {
    cy.intercept('POST', '/api/auth/request-link', { statusCode: 202, body: { ok: true } }).as('requestLink')

    cy.visit('/')
    cy.wait('@me')
    cy.get('input[type="email"]').type('maya@example.com')
    cy.contains('button', 'Send link').click()

    cy.wait('@requestLink')
    cy.contains('maya@example.com')
  })

  it('logs a returning email straight in once the link is verified', () => {
    cy.intercept('POST', '/api/auth/verify', {
      statusCode: 200,
      body: { status: 'logged_in', user: maya, email: null },
    }).as('verify')
    stubCreatePost(maya)

    cy.visit('/?token=returning-token')
    cy.wait('@me')
    cy.wait('@verify')
    cy.wait('@feed')

    // AppShell only shows "Log out" once an identity is set — i.e. on the feed.
    cy.contains('Log out').should('be.visible')
  })

  it('finishes signup with a username, avatar, and first post for a new email', () => {
    cy.intercept('POST', '/api/auth/verify', {
      statusCode: 200,
      body: { status: 'new', user: null, email: 'newbie@example.com' },
    }).as('verify')
    cy.intercept('POST', '/api/auth/signup', {
      statusCode: 200,
      body: { id: 2, username: 'newbie', avatar_url: '/media/avatars/newbie.png', is_bot: false },
    }).as('signup')
    stubCreatePost({ id: 2, username: 'newbie', avatar_url: '/media/avatars/newbie.png', is_bot: false })

    cy.visit('/?token=fresh-token')
    cy.wait('@me')
    cy.wait('@verify')

    cy.contains('newbie@example.com')
    cy.get('input:visible').first().type('newbie')
    cy.get('input[type="file"]').selectFile(
      { contents: Cypress.Buffer.from('not-a-real-png'), fileName: 'avatar.png', mimeType: 'image/png' },
      { force: true },
    )
    cy.get('textarea').first().type('hello there')
    cy.contains('button', 'Post').click()

    cy.wait('@signup')
    cy.wait('@createPost')
    cy.contains('Log out').should('be.visible')
  })

  it('surfaces a verify failure inline and drops back to the email step', () => {
    cy.intercept('POST', '/api/auth/verify', {
      statusCode: 400,
      body: { error: 'This link is invalid or has expired.' },
    }).as('verify')

    cy.visit('/?token=bad-token')
    cy.wait('@me')
    cy.wait('@verify')

    cy.contains('This link is invalid or has expired.')
    // Back on the email step — the email field is present.
    cy.contains('button', 'Send link').should('be.visible')
  })
})

export {}
